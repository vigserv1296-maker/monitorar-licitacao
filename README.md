# 🔔 Monitor — Portal de Compras Públicas

Script que monitora uma sessão pública **24h por dia**, mesmo com o PC desligado,
e envia **e-mail automático** ao detectar qualquer movimentação.

## Como funciona

- Roda nos servidores do GitHub a cada **5 minutos**
- Faz login no portal com suas credenciais
- Compara o conteúdo da sessão com a última verificação
- Envia e-mail instantâneo se detectar mudança

## Configuração (Secrets)

No GitHub, vá em **Settings → Secrets and variables → Actions → New repository secret**
e adicione:

| Secret            | Valor                                      |
|-------------------|--------------------------------------------|
| `PORTAL_USERNAME` | Seu usuário do Portal de Compras Públicas  |
| `PORTAL_PASSWORD` | Sua senha do portal                        |
| `SESSION_CHAVE`   | `467564` (ou a chave da sessão desejada)   |
| `EMAIL_FROM`      | Seu Gmail (vigserv1296@gmail.com)         |
| `EMAIL_PASSWORD`  | App Password do Gmail (16 caracteres)      |
| `EMAIL_TO`        | E-mail que receberá os alertas             |

## Pré-requisito: App Password do Gmail

1. Acesse myaccount.google.com → Segurança → Verificação em duas etapas (ative)
2. Ainda em Segurança → Senhas de app → Criar → copie os 16 caracteres
3. Cole esse código no Secret `EMAIL_PASSWORD`

## Estrutura do projeto

```
monitor-licitacao/
├── .github/
│   └── workflows/
│       └── monitor.yml   ← agenda e roda o script
├── monitor.py             ← lógica principal
├── requirements.txt       ← dependências Python
├── state.json             ← estado salvo entre execuções
└── README.md
```
