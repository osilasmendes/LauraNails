# LauraNails_v2

Novo site da Laura Silva Nail Designer, criado com as imagens reais enviadas.

## Incluído
- Página inicial com slideshow de fotos reais
- Logo da Laura
- Portfólio
- Serviços e valores
- Cadastro de clientes
- Login
- Agendamento com bloqueio de horário ocupado
- Área "Meus agendamentos"
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
