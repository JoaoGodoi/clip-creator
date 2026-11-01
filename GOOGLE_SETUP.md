# Conectar o YouTube (uma vez só, ~5 minutos)

O upload usa a YouTube Data API do Google. Você precisa criar uma credencial
na sua conta — nenhum código seu fica exposto, o arquivo fica só na sua máquina.

## Passo a passo

1. Acesse **https://console.cloud.google.com/** (logado na conta Google do canal
   que vai receber os vídeos).

2. **Crie um projeto**: barra do topo → seletor de projeto → "Novo projeto" →
   nome `podcast-clipper` → Criar (e selecione ele).

3. **Ative a API**: menu ☰ → "APIs e serviços" → "Biblioteca" → busque
   **YouTube Data API v3** → Ativar.

4. **Tela de consentimento**: "APIs e serviços" → "Tela de permissão OAuth"
   (OAuth consent screen) → tipo **Externo** → preencha só o obrigatório
   (nome do app: `Podcast Clipper`, seu e-mail nos dois campos) → Salvar.
   - Em **Público-alvo / Test users**, clique em "Adicionar usuários" e
     adicione **o seu próprio e-mail**. (Enquanto o app está "em teste",
     só e-mails listados aqui conseguem logar.)

5. **Crie a credencial**: "APIs e serviços" → "Credenciais" →
   "Criar credenciais" → **ID do cliente OAuth** → tipo de aplicativo:
   **App para computador (Desktop app)** → Criar.

6. **Baixe o JSON** (botão de download na credencial criada) e salve como:
   ```
   %LOCALAPPDATA%\PodcastClipper\app\client_secret.json
   ```

7. Abra o Podcast Clipper (`run.bat`) → clique em **"Conectar YouTube"** →
   aprove na tela do Google (vai avisar que o app não é verificado — clique
   em "Avançado" → "Acessar Podcast Clipper") → pronto. O login fica salvo
   em `data/token.json` e renova sozinho.

## Limitações do Google que valem saber

- **Uploads via app não verificado nascem como "privado"** no YouTube, mesmo
  que o config peça outra coisa. Você publica/agenda no YouTube Studio com
  2 cliques. (Sai dessa limitação passando o app pela verificação do Google,
  processo chato que só vale a pena mais para frente.)
- **Quota**: por padrão a API dá 10.000 unidades/dia e cada upload custa 1.600
  → ~6 uploads por dia. Dá para pedir aumento no console.
- A thumbnail só sobe automaticamente se a conta tiver verificação por
  telefone (youtube.com/verify). Sem isso, o app ignora e você põe manualmente.
