#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para deletar grupos de recursos com opção de exclusão por nome
Requer: Azure CLI instalado e autenticado (az login já realizado)
Execução: Paralela para melhor performance
Suporta: Filtros de exclusão por padrão, confirmação antes de deletar
"""
import subprocess
import sys
import json
import shutil
import os
import re
from typing import List, Dict, Set
from concurrent.futures import ThreadPoolExecutor, as_completed

class AzureResourceGroupDeleter:
    def __init__(self, verbose: bool = True, max_workers: int = 5, dry_run: bool = False):
        self.verbose = verbose
        self.max_workers = max_workers
        self.dry_run = dry_run
        self.az_command = self.find_az_command()
        self.groups_to_delete = []
        self.groups_to_keep = []
        self.deleted_groups = []
        self.failed_groups = []

    def log(self, message: str):
        """Exibe mensagens de log se verbose estiver ativado"""
        if self.verbose:
            print(f"[INFO] {message}")

    def log_error(self, message: str):
        """Exibe mensagens de erro"""
        print(f"[ERRO] {message}", file=sys.stderr)

    def log_success(self, message: str):
        """Exibe mensagens de sucesso"""
        print(f"[✓] {message}")

    def log_warning(self, message: str):
        """Exibe mensagens de aviso"""
        print(f"[⚠] {message}")

    def format_group_name(self, group_info: Dict) -> str:
        """Formata o nome do grupo com prefixo da assinatura"""
        return f"{group_info['subscription']}.{group_info['name']}"

    def find_az_command(self) -> str:
        """Encontra o comando az no sistema"""
        az_path = shutil.which("az")
        if az_path:
            return az_path

        if sys.platform == "win32":
            az_cmd = shutil.which("az.cmd")
            if az_cmd:
                return az_cmd

            default_paths = [
                os.path.expandvars(r"%ProgramFiles%\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"),
            ]
            for path in default_paths:
                if os.path.exists(path):
                    return path

        return "az"

    def run_command(self, command: List[str], capture_output: bool = True) -> tuple:
        """Executa um comando e retorna (returncode, stdout, stderr)"""
        try:
            result = subprocess.run(
                command,
                capture_output=capture_output,
                text=True,
                check=False,
                shell=sys.platform == "win32"
            )
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            self.log_error(f"Erro ao executar comando: {str(e)}")
            return 1, "", str(e)

    def check_azure_cli(self) -> bool:
        """Verifica se Azure CLI está instalado e autenticado"""
        self.log("Verificando Azure CLI...")
        self.log(f"Usando comando: {self.az_command}")

        returncode, stdout, stderr = self.run_command([self.az_command, "version"])
        if returncode != 0:
            self.log_error("Azure CLI não está instalado ou não está acessível")
            return False

        self.log("✓ Azure CLI encontrado")

        # Verifica se está autenticado
        returncode, stdout, stderr = self.run_command([self.az_command, "account", "show"])
        if returncode != 0:
            self.log_error("Não autenticado na Azure. Execute: az login")
            return False

        self.log("✓ Autenticado na Azure")
        return True

    def get_all_subscriptions(self) -> List[Dict]:
        """Lista todas as assinaturas"""
        self.log("Obtendo todas as assinaturas...")

        returncode, stdout, stderr = self.run_command(
            [self.az_command, "account", "list", "--output", "json"]
        )

        if returncode != 0:
            self.log_error(f"Erro ao listar assinaturas: {stderr}")
            return []

        try:
            subscriptions = json.loads(stdout)
            self.log(f"Encontradas {len(subscriptions)} assinatura(s)")
            return subscriptions
        except json.JSONDecodeError:
            self.log_error("Erro ao processar resposta JSON das assinaturas")
            return []

    def get_resource_groups_in_subscription(self, subscription_id: str) -> List[Dict]:
        """Lista grupos de recursos de uma assinatura específica"""
        returncode, stdout, stderr = self.run_command(
            [self.az_command, "group", "list", "--subscription", subscription_id, "--output", "json"]
        )

        if returncode != 0:
            self.log_error(f"Erro ao listar grupos da assinatura {subscription_id}: {stderr}")
            return []

        try:
            groups = json.loads(stdout)
            return groups
        except json.JSONDecodeError:
            self.log_error(f"Erro ao processar grupos da assinatura {subscription_id}")
            return []

    def should_exclude_group(self, group_name: str, exclude_patterns: List[str]) -> bool:
        """Verifica se o grupo deve ser excluído baseado nos padrões"""
        for pattern in exclude_patterns:
            try:
                # Tenta primeiro uma correspondência exata (case-insensitive)
                if group_name.lower() == pattern.lower():
                    return True
                # Depois tenta como regex
                if re.search(pattern, group_name, re.IGNORECASE):
                    return True
            except re.error:
                self.log_warning(f"Padrão regex inválido: {pattern}")
                continue
        return False

    def collect_groups(self, exclude_patterns: List[str]) -> bool:
        """Coleta todos os grupos de recursos de todas as assinaturas"""
        if not self.check_azure_cli():
            return False

        subscriptions = self.get_all_subscriptions()

        if not subscriptions:
            self.log_warning("Nenhuma assinatura encontrada")
            return False

        self.log(f"Processando {len(subscriptions)} assinatura(s)...")

        all_groups = []
        for subscription in subscriptions:
            sub_id = subscription['id']
            sub_name = subscription.get('name', 'Unknown')
            self.log(f"Listando grupos da assinatura: {sub_name}")

            groups = self.get_resource_groups_in_subscription(sub_id)
            for group in groups:
                all_groups.append({
                    'subscription_id': sub_id,
                    'subscription_name': sub_name,
                    'group': group
                })

        # Classifica em "deletar" e "manter"
        for item in all_groups:
            group_name = item['group']['name']
            sub_name = item['subscription_name']

            group_info = {
                'name': group_name,
                'subscription': sub_name,
                'id': item['group']['id'],
                'subscription_id': item['subscription_id']
            }

            if self.should_exclude_group(group_name, exclude_patterns):
                self.groups_to_keep.append(group_info)
            else:
                self.groups_to_delete.append(group_info)

        return True

    def delete_resource_group(self, group_info: Dict) -> bool:
        """Deleta um grupo de recursos específico"""
        group_name = group_info['name']
        subscription_id = group_info['subscription_id']
        formatted_name = self.format_group_name(group_info)
        
        if self.dry_run:
            self.log(f"[DRY-RUN] Seria deletado: {formatted_name}")
            return True

        self.log(f"Deletando grupo: {formatted_name}")

        returncode, stdout, stderr = self.run_command(
            [self.az_command, "group", "delete", 
             "--name", group_name,
             "--subscription", subscription_id,
             "--yes", "--no-wait"]
        )

        if returncode != 0:
            self.log_error(f"Erro ao deletar '{formatted_name}': {stderr}")
            return False

        return True

    def delete_groups_parallel(self) -> None:
        """Deleta grupos em paralelo"""
        if not self.groups_to_delete:
            self.log_warning("Nenhum grupo para deletar")
            return

        self.log(f"Iniciando deleção de {len(self.groups_to_delete)} grupo(s) em paralelo...")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.delete_resource_group, group): 
                group
                for group in self.groups_to_delete
            }

            for future in as_completed(futures):
                group_info = futures[future]
                formatted_name = self.format_group_name(group_info)
                try:
                    if future.result():
                        self.deleted_groups.append(formatted_name)
                        self.log_success(f"Deletado com sucesso: {formatted_name}")
                    else:
                        self.failed_groups.append(formatted_name)
                except Exception as e:
                    self.failed_groups.append(formatted_name)
                    self.log_error(f"Exceção ao deletar '{formatted_name}': {str(e)}")

    def display_summary(self) -> None:
        """Exibe um resumo das operações"""
        print("")
        print("="*80)
        print("RESUMO DA OPERAÇÃO")
        print("="*80)
        print("")

        if self.dry_run:
            print("[DRY-RUN] Modo simulação ativado - nenhum grupo foi realmente deletado")
            print("")

        print(f"Grupos a manter (excluídos): {len(self.groups_to_keep)}")
        if self.groups_to_keep:
            for group in self.groups_to_keep:
                formatted_name = self.format_group_name(group)
                print(f"   ✓ {formatted_name}")
        print("")

        print(f"Grupos deletados com sucesso: {len(self.deleted_groups)}")
        if self.deleted_groups:
            for formatted_name in self.deleted_groups:
                print(f"   ✓ {formatted_name}")
        print("")

        print(f"Grupos que falharam na deleção: {len(self.failed_groups)}")
        if self.failed_groups:
            for formatted_name in self.failed_groups:
                print(f"   ✗ {formatted_name}")
        print("")

        print(f"Grupos identificados para deleção: {len(self.groups_to_delete)}")
        print("="*80)

    def display_groups_preview(self) -> None:
        """Exibe uma prévia dos grupos que serão deletados"""
        print("")
        print("="*80)
        print("PRÉVIA: GRUPOS PARA DELETAR")
        print("="*80)
        print("")

        if not self.groups_to_delete:
            print("Nenhum grupo será deletado.")
            print("")
            return

        print(f"Total de grupos a deletar: {len(self.groups_to_delete)}")
        print("")

        # Agrupa por assinatura
        by_subscription = {}
        for group in self.groups_to_delete:
            sub = group['subscription']
            if sub not in by_subscription:
                by_subscription[sub] = []
            by_subscription[sub].append(group)

        for sub_name in sorted(by_subscription.keys()):
            print(f"Assinatura: {sub_name}")
            for group in by_subscription[sub_name]:
                formatted_name = self.format_group_name(group)
                print(f"   • {formatted_name}")
            print("")

        print("="*80)
        print("")

        if self.groups_to_keep:
            print("="*80)
            print("GRUPOS QUE SERÃO MANTIDOS (EXCLUÍDOS)")
            print("="*80)
            print("")

            by_subscription = {}
            for group in self.groups_to_keep:
                sub = group['subscription']
                if sub not in by_subscription:
                    by_subscription[sub] = []
                by_subscription[sub].append(group)

            for sub_name in sorted(by_subscription.keys()):
                print(f"Assinatura: {sub_name}")
                for group in by_subscription[sub_name]:
                    formatted_name = self.format_group_name(group)
                    print(f"   ✓ {formatted_name}")
                print("")


            print("="*80)

    def confirm_deletion(self) -> bool:
        """Solicita confirmação do usuário antes de deletar"""
        if self.dry_run:
            print("\n[DRY-RUN] Simulando deleção sem realmente deletar grupos.")
            return True

        if not self.groups_to_delete:
            return False

        self.display_groups_preview()

        print("\n⚠️  ATENÇÃO: Esta operação é IRREVERSÍVEL!")
        print(f"Você está prestes a deletar {len(self.groups_to_delete)} grupo(s) de recursos.")
        print(f"Serão mantidos {len(self.groups_to_keep)} grupo(s).")
        print("")

        while True:
            response = input("Deseja continuar? (s/n): ").strip().lower()
            if response in ['s', 'sim', 'y', 'yes']:
                return True
            elif response in ['n', 'nao', 'não', 'no']:
                print("Operação cancelada pelo usuário.")
                return False
            else:
                print("Resposta inválida. Digite 's' para sim ou 'n' para não.")

    def delete_resource_groups(self, exclude_patterns: List[str]) -> bool:
        """Função principal para deletar grupos de recursos"""
        # Coleta grupos
        if not self.collect_groups(exclude_patterns):
            return False

        # Confirma com usuário
        if not self.confirm_deletion():
            return False

        # Deleta em paralelo
        if self.groups_to_delete:
            self.delete_groups_parallel()

        # Exibe resumo
        self.display_summary()

        return len(self.failed_groups) == 0


def main():
    """Função principal"""
    import argparse


    parser = argparse.ArgumentParser(
        description="Delete grupos de recursos da Azure com opção de exclusão"
    )
    parser.add_argument(
        "--exclude",
        type=str,
        nargs="+",
        default=[],
        help="Padrões de nomes a excluir (exato ou regex). Ex: --exclude rg-prod rg-important 'rg-*-prod'"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=5,
        help="Número de workers paralelos (padrão: 5)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Modo silencioso (menos logs)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Modo simulação - lista grupos sem realmente deletar"
    )

    args = parser.parse_args()

    deleter = AzureResourceGroupDeleter(
        verbose=not args.quiet,
        max_workers=args.workers,
        dry_run=args.dry_run
    )

    success = deleter.delete_resource_groups(args.exclude)

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
