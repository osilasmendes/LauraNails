# LauraNails_v2

Novo site da Laura Silva Nail Designer, criado com as imagens reais enviadas.

## Incluído
- Página inicial com portfólio de fotos reais
- Logo da Laura
- Portfólio
- Serviços e valores
- Cadastro de clientes
- Login com WhatsApp e senha ou conta Google
- Calendário mensal com horários disponíveis e bloqueio de reservas duplicadas
- Próximos horários e histórico em "Meus agendamentos"
- Painel administrativo
- Banco SQLite local
- PostgreSQL no Render
- render.yaml pronto

## Rodar no VS Code

No terminal:

python -m venv venv

No PowerShell, se a ativação for bloqueada, não precisa ativar. Use:

.\venv\Scripts\python.exe -m pip install -r requirements.txt

Para criar o admin localmente:

$env:ADMIN_USER="laura.laura"
$env:ADMIN_PASSWORD="SUA_SENHA"

Depois:

.\venv\Scripts\python.exe app.py

Abra:
http://127.0.0.1:5000

## Render

No Render, defina:
- ADMIN_USER = laura.laura
- ADMIN_PASSWORD = escolha uma senha segura
- SECRET_KEY = pode ser gerada pelo Render
- DATABASE_URL = será ligada ao PostgreSQL

Nunca coloque a senha real diretamente no GitHub.

## Alterações desta versão
- Logo substituída por arquivo de melhor qualidade
- Preços protegidos por login
- Tabela de preços não aparece para visitantes


## Login com Google

Crie um cliente OAuth do tipo **Aplicativo da Web** no Google Cloud.
Nos URIs de redirecionamento autorizados, cadastre a URL pública do site
com o caminho `/login/google/callback`. Para testar localmente, cadastre
também `http://127.0.0.1:5000/login/google/callback`.

Configure `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` e
`GOOGLE_REDIRECT_URI` no ambiente, além de manter a `SECRET_KEY` estável.
O botão aparece quando as quatro variáveis estão configuradas. Se o
aplicativo OAuth estiver em teste, adicione as contas de teste no Google Cloud.

Clientes existentes entram uma vez com WhatsApp e senha e usam **Meu perfil
→ Vincular conta Google**. O vínculo usa o identificador do Google e mantém
o mesmo cadastro e o mesmo histórico. O primeiro login de uma nova cliente
solicita WhatsApp para contato. A administração usa seu acesso atual.

A atualização cria a tabela de vínculos no banco existente na primeira
requisição. Preserve a configuração de `DATABASE_URL` do serviço atual.
