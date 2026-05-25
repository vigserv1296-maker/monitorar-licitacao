import requests
from bs4 import BeautifulSoup
import hashlib
import os
import smtplib
import json
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─── Configurações (vindas dos Secrets do GitHub) ───────────────────────────
SESSION_URL    = os.environ.get('SESSION_URL', 'https://www.portaldecompraspublicas.com.br/processos/es/fundacao-inova-capixaba-2904/pe-030-2026-2026-467564')
EMAIL_FROM     = os.environ.get('EMAIL_FROM')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
EMAIL_TO       = os.environ.get('EMAIL_TO')
STATE_FILE     = 'state.json'

# ─── Busca conteúdo público da sessão ───────────────────────────────────────
def get_session_html():
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/124.0 Safari/537.36'
        )
    }
    resp = requests.get(SESSION_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text

# ─── Extrai apenas o andamento do processo ──────────────────────────────────
def extract_timeline(html):
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'meta', 'link', 'noscript', 'head', 'footer', 'nav']):
        tag.decompose()
    return soup.get_text(separator=' ', strip=True)

def sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

# ─── Estado persistente ──────────────────────────────────────────────────────
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'hash': None, 'last_check': None, 'last_change': None, 'checks': 0}

def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

# ─── Envio de e-mail ─────────────────────────────────────────────────────────
def send_email(subject, headline, message):
    now = datetime.now().strftime('%d/%m/%Y às %H:%M')

    html = f"""
    <html><body style="font-family:Arial,sans-serif;background:#f0f2f5;padding:20px">
      <div style="max-width:560px;margin:auto;background:#fff;border-radius:8px;
                  overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.15)">
        <div style="background:#003580;padding:24px;text-align:center">
          <h2 style="color:#fff;margin:0;font-size:20px">{headline}</h2>
          <p style="color:#aac4e8;margin:6px 0 0;font-size:13px">
            Portal de Compras Públicas · PE 030/2026
          </p>
        </div>
        <div style="padding:24px">
          <p style="font-size:15px;color:#333">{message}</p>
          <table style="width:100%;font-size:13px;color:#555;margin:16px 0">
            <tr><td><b>Processo:</b></td><td>PE 030/2026 – Inova Capixaba</td></tr>
            <tr><td><b>Horário:</b></td><td>{now}</td></tr>
          </table>
          <a href="{SESSION_URL}"
             style="display:inline-block;background:#003580;color:#fff;
                    padding:12px 24px;border-radius:6px;text-decoration:none;
                    font-size:14px;font-weight:bold">
            📋 Acessar Processo Agora
          </a>
        </div>
        <div style="background:#f7f7f7;padding:12px 24px;font-size:11px;color:#999">
          Alerta automático — monitor-licitacao
        </div>
      </div>
    </body></html>
    """

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = EMAIL_FROM
    msg['To']      = EMAIL_TO
    msg.attach(MIMEText(html, 'html'))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as srv:
        srv.login(EMAIL_FROM, EMAIL_PASSWORD)
        srv.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

    print(f'📧 E-mail enviado para {EMAIL_TO}')

# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    now_str = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    print(f'\n🔍 [{now_str}] Verificando processo PE 030/2026...')

    state = load_state()
    state['checks'] = state.get('checks', 0) + 1

    try:
        html  = get_session_html()
        text  = extract_timeline(html)
        h     = sha256(text)

        print(f'   Hash: {h[:20]}...')

        if state['hash'] is None:
            print('📝 Primeira execução — salvando estado inicial.')
            state['hash']       = h
            state['last_check'] = now_str
            save_state(state)
            send_email(
                '✅ Monitor Ativado — PE 030/2026',
                '✅ Monitor Ativado com Sucesso!',
                'O monitoramento está rodando 24h. Você receberá alertas assim que houver qualquer movimentação no processo.'
            )

        elif h != state['hash']:
            print('🚨 MUDANÇA DETECTADA!')
            state['hash']        = h
            state['last_change'] = now_str
            state['last_check']  = now_str
            save_state(state)
            send_email(
                '🚨 MOVIMENTAÇÃO DETECTADA — PE 030/2026',
                '🚨 Movimentação Detectada!',
                'Houve uma alteração no processo. Acesse agora para verificar mensagens, lances ou mudanças de status.'
            )

        else:
            print('✅ Sem alterações.')
            state['last_check'] = now_str
            save_state(state)

    except Exception as exc:
        print(f'❌ Erro: {exc}')
        try:
            send_email(
                '⚠️ Erro no Monitor — PE 030/2026',
                '⚠️ Erro no Monitoramento',
                f'Não foi possível verificar o processo.<br><br><b>Detalhe:</b> {exc}'
            )
        except Exception as mail_err:
            print(f'   (Falha ao enviar e-mail de erro: {mail_err})')
        raise

if __name__ == '__main__':
    main()
