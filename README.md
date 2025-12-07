# Azure Resource Group Deleter v1.0

Documentação Técnica do script de deleção de Grupos de Recursos no Microsoft Azure, focado em automação segura, previsível e auditável.

---

## 1. Visão Geral 📋

O script `delete_azure_resource_groups.py` foi criado para automatizar a deleção em massa de Resource Groups no Azure de forma controlada e com foco em segurança operacional.
Ele permite proteger grupos críticos via filtros, simular previamente o impacto das deleções e executar operações em paralelo para reduzir o tempo total de execução.

Principais capacidades:

- Exclusão seletiva de grupos de recursos por nome ou por padrões baseados em expressões regulares.
- Modo de simulação (*dry-run*) para visualizar o que seria apagado antes de executar de fato.
- Deleção paralela com controle do número de *workers* para melhor desempenho.
- Confirmação interativa antes de ações irreversíveis (quando não estiver em *dry-run*).

---

## 2. Pré‑requisitos 📦

### 2.1 Azure CLI instalado

O script depende do Azure CLI (`az`) instalado e disponível no `PATH` do sistema.
Certifique-se de que o comando abaixo funciona sem erros:

az version


Se o Azure CLI não estiver instalado, consulte a documentação oficial da Microsoft para instalação no seu sistema operacional.

### 2.2 Autenticação no Azure 🔑

O script assume que a sessão já está autenticada no Azure por meio do `az login`.
Você pode validar a sessão com:

az account show

Se não estiver autenticado:

az login


### 2.3 Permissões necessárias

A conta utilizada deve possuir permissões suficientes para deletar Resource Groups.

- Função mínima recomendada: **Contributor** ou **Owner** na(s) assinatura(s) alvo.
- Escopo: permissão de **Delete** sobre Resource Groups.

Para revisar as permissões associadas:

az role assignment list -o table


---

## 3. Parâmetros de Execução 🚀

### Sintaxe básica

python3 delete_azure_resource_groups.py


### 3.1 `--exclude`

- **Tipo:** lista de strings (um ou mais valores).
- **Default:** vazio (nenhum grupo é protegido por padrão).
- **Função:** define padrões de nome que serão sempre protegidos contra deleção.

Suporta:

- Correspondência exata (case-insensitive), por exemplo: `--exclude rg-prod`.
- Expressões regulares, por exemplo: `--exclude "^rg-.*-prod$"`.

Exemplos:

Proteger grupos específicos por nome
python3 delete_azure_resource_groups.py --exclude rg-prod rg-core rg-infra

Proteger qualquer grupo que contenha "prod" no nome (regex simples)
python3 delete_azure_resource_groups.py --exclude "prod"

Proteger grupos que terminem com "-important"
python3 delete_azure_resource_groups.py --exclude ".*-important$"


### 3.2 `--workers`

- **Tipo:** inteiro.
- **Default:** `5`.
- **Faixa recomendada:** 1 a 20.
- **Função:** define o número de deleções realizadas em paralelo.

Impacto esperado:

- Valores baixos (1–3): execução mais lenta, menor consumo de recursos e menor chance de *throttling*.
- Valores médios (5–10): bom equilíbrio entre velocidade e estabilidade.
- Valores altos (15+): maior risco de *throttling* nas APIs do Azure.

Exemplos:

python3 delete_azure_resource_groups.py --workers 3
python3 delete_azure_resource_groups.py --workers 15


### 3.3 `--quiet`

- **Tipo:** flag booleana (sem valor).
- **Default:** desabilitado (modo verboso).
- **Função:** reduz a quantidade de logs informativos, mantendo apenas o essencial.

Exemplo:

python3 delete_azure_resource_groups.py --quiet


### 3.4 `--dry-run`

- **Tipo:** flag booleana (sem valor).
- **Default:** desabilitado (execução real).
- **Função:** modo de simulação, que apenas lista o que seria deletado, sem executar deleções.

No modo *dry-run*:

- Lista todos os grupos encontrados.
- Indica quais seriam deletados.
- Indica quais seriam mantidos (por conta de `--exclude`)
- Nenhum comando de deleção é emitido de fato.

É altamente recomendável sempre validar a configuração com `--dry-run` antes da execução real.

Exemplos:

python3 delete_azure_resource_groups.py --dry-run
python3 delete_azure_resource_groups.py --dry-run --exclude "prod" "core"


---

## 4. Fluxo de Execução

O fluxo de alto nível é:

1. **Validação inicial:** verifica se o Azure CLI está disponível e se existe sessão autenticada.
2. **Coleta de grupos:** lista assinaturas e grupos de recursos, classificando-os em “deletar” e “manter” conforme os filtros.
3. **Prévia (preview):** apresenta um resumo dos grupos que seriam deletados e dos que serão preservados.
4. **Confirmação:** solicita confirmação do usuário antes de iniciar as deleções (não é exibido em `--dry-run`).
5. **Deleção paralela:** executa deleções em paralelo até o limite definido em `--workers`.
6. **Resumo final:** mostra estatísticas de sucesso, falha e status geral da execução.

---

## 5. Exemplos de Uso Prático

### 5.1 Limpeza segura (recomendado para iniciantes)


Passo 1: Simular para ver o que será deletado
python3 delete_azure_resource_groups.py --dry-run

Passo 2: Executar de verdade, se estiver tudo correto
python3 delete_azure_resource_groups.py


### 5.2 Deletar tudo exceto produção

Simulação inicial (recomendado)
python3 delete_azure_resource_groups.py --dry-run
--exclude "prod" "production" ".*-prd$"

Execução real após validação do preview
python3 delete_azure_resource_groups.py
--exclude "prod" "production" ".*-prd$"


### 5.3 Performance elevada em grande volume

Para ambientes com mais de 50 Resource Groups, é possível aumentar o paralelismo, sempre com filtros de proteção.

python3 delete_azure_resource_groups.py
--exclude "prod" "core"
--workers 12
--quiet


### 5.4 Uso em pipeline CI/CD

É possível integrar o script em pipelines, mantendo etapas de segurança e aprovação.

Em ambiente de homologação, sempre com dry-run
python3 delete_azure_resource_groups.py
--dry-run
--exclude "prod"
--quiet

Em produção, sem dry-run, mas ainda com exclusões e workers controlados
python3 delete_azure_resource_groups.py
--exclude "prod"
--workers 8


---

## 6. Códigos de Saída

O script utiliza códigos de saída simples para integração com CI/CD e automações.

| Código | Significado | Quando ocorre                                              |
| ------ | ----------- | ---------------------------------------------------------- |
| 0      | Sucesso     | Todas as operações previstas finalizaram sem falhas.       |
| 1      | Falha       | Alguma deleção falhou ou houve erro de validação/execução. |

---

## 7. Mensagens de Status

As mensagens de log usam prefixos visuais para facilitar a leitura.

| Prefixo  | Tipo        | Exemplo de uso                            |
| -------- | ----------- | ----------------------------------------- |
| `[INFO]` | Informativo | `[INFO] Obtendo todas as assinaturas...`  |
| `[✓]`    | Sucesso     | `[✓] Deletado com sucesso: prod.rg-temp`  |
| `[✗]`    | Falha       | `[✗] Erro ao deletar 'prod.rg-temp'`      |
| `[⚠]`    | Aviso       | `[⚠] Nenhum grupo para deletar`           |
| `[ERRO]` | Crítico     | `[ERRO] Não autenticado na Azure`         |
| `[DRY-RUN]` | Simulação | `[DRY-RUN] Seria deletado: prod.rg-temp` |

---

## 8. Troubleshooting ⚠️

### Problema: Azure CLI não está instalado

- Verifique se o binário existe e está no `PATH`.
- Revise a instalação conforme o seu sistema operacional.

Comandos úteis:

which az
az version


### Problema: não autenticado na Azure

- Realize login interativo com o Azure CLI.

az login

ou, se necessário:
az login --use-device-code


### Problema: erro ao listar grupos da assinatura

Possíveis causas:

- Falta de permissão (ausência de funções como Contributor ou Owner).
- Assinatura desativada ou removida. 
- Credenciais expiradas ou sessão inválida.

Ações recomendadas:

az logout
az login
az role assignment list -o table


---

## 9. Performance e Limites

Abaixo, uma referência aproximada para escolha de `--workers` de acordo com o volume de Resource Groups.

| Qtd. de grupos | Workers recomendados | Tempo estimado*  |
| -------------- | -------------------- | ---------------- |
| < 10           | 3–5                  | < 5 minutos      |
| 10–50          | 5–8                  | 5–15 minutos     |
| 50–100         | 8–12                 | 15–30 minutos    |
| > 100          | 12–15                | 30+ minutos      |

\*Os tempos dependem da complexidade dos recursos contidos em cada grupo (VMs, redes, discos etc.).

---

## 10. Boas Práticas de Segurança

Alguns cuidados recomendados ao usar o script em ambientes reais:

- Sempre iniciar com `--dry-run` para validar o escopo das deleções.
- Proteger recursos críticos com filtros em `--exclude` (por exemplo: `"prod"`, `"core"`, `"critical"`, `".*-important$"`).
- Executar em janelas de menor uso, para evitar impacto em ambientes produtivos.
- Revisar os logs após a execução para fins de auditoria e compliance.
- Manter *backups* ou estratégias de recuperação antes de remover recursos importantes, quando aplicável.
- Em pipelines de CI/CD, considerar etapas de *manual approval* antes de qualquer deleção real.

---

## 11. Referências Úteis

Para aprofundar o entendimento sobre os componentes envolvidos:

- Documentação oficial do **Azure CLI**.
- Conceitos e boas práticas de **Azure Resource Groups**.
- Módulo `subprocess` da linguagem Python.
- Módulo `concurrent.futures` da linguagem Python para paralelismo.

---

## 12. Licença e Direitos Autorais
Este projeto é de uso educacional, focado em práticas de DevOps e Cloud Computing com Azure.

Copyright
Prof. João Menk

Considere manter esta atribuição ao reutilizar ou adaptar este código em outros contextos acadêmicos ou profissionais.
