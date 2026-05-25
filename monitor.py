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
PORTAL_USERNAME = os.environ.get('PORTAL_USERNAME')
PORTAL_PASSWORD = os.environ.get('PORTAL_PASSWORD')
SESSION_CHAVE   = os.environ.get('SESSION_CHAVE', '467564')
EMAIL_FROM      = os.environ.get('EMAIL_FROM')
EMAIL_PASSWORD  = os.environ.get('EMAIL_PASSWORD')   # App Password do Gmail
EMAIL_TO        = os.environ.get('EMAIL_TO')
STATE_FILE      = 'state.json'

# ─── Login no portal (OAuth2 / Keycloak) ────────────────────────────────────
def login_portal():
    session = requests.Session()
    session.headers.update({
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/124.0 Safari/537.36'
        )
    })

    login_url = (
        'https://iam.secure.portaldecompraspublicas.com.br'
        '/realms/Portal/protocol/openid-connect/auth'
    )
    params = {
        'client_id':     'aspclient',
        'redirect_uri':  'https://operacao.portaldecompraspublicas.com.br/18/loginext/oAuth/',
        'response_type': 'code',
        'scope':         'openid',
    }

    resp = session.get(login_url, params=params, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, 'html.parser')
    form = soup.find('form', {'id': 'kc-form-login'}) or soup.find('form')
    if not form:
        raise RuntimeError('Formulário de login não encontrado.')

    # Captura campos ocultos (CSRF etc.)
    action_url  = form['action']
    hidden_data = {
        inp['name']: inp.get('value', '')
        for inp in form.find_all('input', {'type': 'hidden'})
        if inp.get('name')
    }
    hidden_data.update({'username': PORTAL_USERNAME, 'password': PORTAL_PASSWORD})

    resp2 = session.post(action_url, data=hidden_data, allow_redirects=True, timeout=30)

    if 'login' in resp2.url.lower() or 'incorret' in resp2.text.lower():
        raise RuntimeError('Login falhou — verifique usuário e senha nos Secrets.')

    print('✅ Login bem-sucedido')
    return session


# ─── Busca conteúdo da sessão ────────────────────────────────────────────────
def get_session_html(session):
    url = (
        f'https://operacao.portaldecompraspublicas.com.br'
        f'/4/SessaoPublica/?ttCD_CHAVE={SESSION_CHAVE}'
    )
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


# ─── Extrai texto relevante (sem scripts/estilos) ───────────────────────────
def extract_text(html):
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'meta', 'link', 'noscript', 'head']):
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
    session_url = (
        f'https://operacao.portaldecompraspublicas.com.br'
        f'/4/SessaoPublica/?ttCD_CHAVE={SESSION_CHAVE}'
    )

    html = f"""
    <html><body style="font-family:Arial,sans-serif;background:#f0f2f5;padding:20px">
      <div style="max-width:560px;margin:auto;background:#fff;border-radius:8px;
                  overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.15)">
        <div style="background:#003580;padding:24px;text-align:center">
          <h2 style="color:#fff;margin:0;font-size:20px">{headline}</h2>
          <p  style="color:#aac4e8;margin:6px 0 0;font-size:13px">
            Portal de Compras Públicas · Sessão {SESSION_CHAVE}
          </p>
        </div>
        <div style="padding:24px">
          <p style="font-size:15px;color:#333">{message}</p>
          <table style="width:100%;font-size:13px;color:#555;margin:16px 0">
            <tr><td><b>Sessão:</b></td><td>{SESSION_CHAVE}</td></tr>
            <tr><td><b>Horário:</b></td><td>{now}</td></tr>
          </table>
          <a href="{session_url}"
             style="display:inline-block;background:#003580;color:#fff;
                    padding:12px 24px;border-radius:6px;text-decoration:none;
                    font-size:14px;font-weight:bold">
            📋 Acessar Sessão Agora
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
    print(f'\n🔍 [{now_str}] Verificando sessão {SESSION_CHAVE}...')

    state = load_state()
    state['checks'] = state.get('checks', 0) + 1

    try:
        session = login_portal()
        html    = get_session_html(session)
        text    = extract_text(html)
        h       = sha256(text)

        print(f'   Hash: {h[:20]}...')

        if state['hash'] is None:
            # Primeira execução
            print('📝 Primeira execução — salvando estado inicial.')
            state['hash']        = h
            state['last_check']  = now_str
            save_state(state)
            send_email(
                '✅ Monitor Ativado — Sessão ' + SESSION_CHAVE,
                '✅ Monitor Ativado com Sucesso!',
                'O monitoramento está rodando 24h. Você receberá alertas assim que houver qualquer movimentação nesta sessão.'
            )

        elif h != state['hash']:
            # Mudança detectada!
            print('🚨 MUDANÇA DETECTADA!')
            state['hash']         = h
            state['last_change']  = now_str
            state['last_check']   = now_str
            save_state(state)
            send_email(
                '🚨 MOVIMENTAÇÃO DETECTADA — Sessão ' + SESSION_CHAVE,
                '🚨 Movimentação Detectada!',
                'Houve uma alteração na sessão pública. Acesse agora para verificar lances, mensagens ou mudanças de status.'
            )

        else:
            print('✅ Sem alterações.')
            state['last_check'] = now_str
            save_state(state)

    except Exception as exc:
        print(f'❌ Erro: {exc}')
        try:
            send_email(
                '⚠️ Erro no Monitor — Sessão ' + SESSION_CHAVE,
                '⚠️ Erro no Monitoramento',
                f'Não foi possível verificar a sessão.<br><br><b>Detalhe:</b> {exc}'
            )
        except Exception as mail_err:
            print(f'   (Falha ao enviar e-mail de erro: {mail_err})')
        raise


if __name__ == '__main__':
    main()
