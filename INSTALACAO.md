# 🛠️ Instalação do Podcast Clipper — do zero, comando por comando

Guia para instalar num PC **Windows 10/11** que não tem nada instalado.
Todos os comandos são para o **PowerShell** (botão Iniciar → digite `PowerShell` → abrir).

> ⏱️ Tempo total: ~30–60 min (a maior parte é download).
> 💾 Espaço: ~15 GB livres (modelos de IA + vídeos baixados).

---

## 0. O que o app precisa

| Programa | Para quê | Obrigatório? |
|---|---|---|
| Python 3.12 | roda o app | ✅ sim |
| FFmpeg | corta e renderiza os vídeos | ✅ sim |
| Ollama + modelo `qwen3:8b` | IA local (grátis) que escolhe os melhores cortes | ✅ sim (ou use a API do Claude, ver passo 8) |
| Placa de vídeo NVIDIA | transcrição rápida | ❌ opcional — sem ela roda na CPU, só que bem mais lento |

---

## 1. Conferir se o `winget` funciona

O `winget` é o instalador de programas do próprio Windows. Teste:

```powershell
winget --version
```

Se aparecer um número de versão (ex.: `v1.9.xxxx`), segue. Se der erro, instale o
**"App Installer"** pela Microsoft Store e abra um PowerShell novo.

---

## 2. Instalar o Python 3.12

```powershell
winget install -e --id Python.Python.3.12
```

**Feche o PowerShell e abra outro** (para ele enxergar o Python novo) e confira:

```powershell
py -3.12 --version
```

Deve mostrar `Python 3.12.x`.

---

## 3. Instalar o FFmpeg

```powershell
winget install -e --id Gyan.FFmpeg
```

Feche e abra o PowerShell de novo e confira:

```powershell
ffmpeg -version
```

> Se disser que o comando não existe, não tem problema: o app procura o FFmpeg
> sozinho na pasta onde o winget instala. Só siga em frente.

---

## 4. Instalar o Ollama e baixar o modelo de IA

```powershell
winget install -e --id Ollama.Ollama
```

Feche e abra o PowerShell e baixe o modelo (~5 GB, demora um pouco):

```powershell
ollama pull qwen3:8b
```

Confira se baixou:

```powershell
ollama list
```

Deve aparecer `qwen3:8b` na lista.

> 💡 Se o PC for fraco (pouca RAM/sem GPU), dá para usar um modelo menor:
> `ollama pull qwen3:4b` e depois trocar `ollama_model: qwen3:4b` no `config.yaml`.

---

## 5. (Só se tiver placa NVIDIA) Atualizar o driver

Baixe e instale o driver mais recente da sua placa em
**https://www.nvidia.com/pt-br/drivers/** (ou pelo app NVIDIA). Depois confira:

```powershell
nvidia-smi
```

Se aparecer uma tabela com o nome da placa, tá ok. Não precisa instalar CUDA
separado — as bibliotecas vêm junto com o `pip` no próximo passo.

Sem placa NVIDIA? Pula este passo, o app usa a CPU automaticamente.

---

## 6. Colocar a pasta do projeto no PC

Copie a pasta `podcast_clipper` (pendrive, zip, Drive…) para a **Área de Trabalho**.
O caminho deve ficar assim:

```
C:\Users\SEU_USUARIO\Desktop\podcast_clipper
```

> ⚠️ Quem estiver mandando: **não precisa** mandar as pastas `.venv`, `data`, `output`
> e `__pycache__` (são geradas no PC de cada um e têm vários GB). Também **não mande**
> `client_secret.json` nem `data\token.json` — são as credenciais do seu YouTube.

Entre na pasta pelo PowerShell:

```powershell
cd "$env:USERPROFILE\Desktop\podcast_clipper"
```

---

## 7. Criar o ambiente Python e instalar as dependências

Ainda dentro da pasta do projeto:

```powershell
py -3.12 -m venv .venv
```

```powershell
.venv\Scripts\python.exe -m pip install --upgrade pip
```

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Isso baixa ~3 GB (as bibliotecas da NVIDIA são grandes). Espere terminar sem erro vermelho.

Teste rápido se tudo importa:

```powershell
.venv\Scripts\python.exe -c "import fastapi, yt_dlp, faster_whisper, PIL, yaml; print('OK')"
```

Tem que aparecer `OK`.

---

## 8. (Opcional) Usar a API do Claude em vez do Ollama

O padrão é o Ollama (grátis, local). Se quiser mais qualidade na escolha dos cortes
e tiver uma chave da API da Anthropic:

```powershell
setx ANTHROPIC_API_KEY "sua-chave-aqui"
```

E no `config.yaml` troque:

```yaml
llm:
  provider: anthropic
```

Feche e abra o PowerShell depois do `setx`.

---

## 9. (Opcional) Baixar os vídeos de fundo do "modo dopamina"

Os gameplays de fundo dos shorts (Subway Surfers, Minecraft parkour, GTA) são
pesados (~1,7 GB) e podem não ter vindo na pasta. Para baixar de novo
(estão listados em `assets\dopamine\FONTES.md`), dentro da pasta do projeto:

```powershell
.venv\Scripts\python.exe -m yt_dlp -f "bv*[height<=1080][ext=mp4]" -o "assets\dopamine\subway_surfers.mp4" "https://www.youtube.com/watch?v=i0M4ARe9v0Y"
```

```powershell
.venv\Scripts\python.exe -m yt_dlp -f "bv*[height<=1080][ext=mp4]" -o "assets\dopamine\gta_mega_ramp.mp4" "https://www.youtube.com/watch?v=ZtLrNBdXT7M"
```

```powershell
.venv\Scripts\python.exe -m yt_dlp -f "bv*[height<=1080][ext=mp4]" -o "assets\dopamine\minecraft_parkour.mp4" "https://www.youtube.com/watch?v=952ILTHDgC4"
```

> O Minecraft parkour pede crédito ao canal na descrição.

Sem esses arquivos o app funciona normal, só o "modo dopamina" fica desligado.

---

## 10. Personalizar

Abra o `config.yaml` no Bloco de Notas:

```powershell
notepad config.yaml
```

O que vale mexer:

- `podcast.nome` → nome do podcast de onde vêm os cortes (vai nos créditos).
- `whisper.model` → `medium` é o padrão. PC sem GPU: use `small` (mais rápido).
- `cuts.long.count` / `cuts.shorts.count` → quantos cortes gerar por vídeo.
- `render.parallel_renders` → PC fraco: coloque `1`.

**Ending (outro) dos cortes longos:** o `assets\outro.mp4` atual é do canal de quem
te passou o projeto. Para não usar, apague:

```powershell
Remove-Item assets\outro.mp4
```

Se quiser uma intro/ending sua, coloque `assets\intro.mp4` e/ou `assets\outro.mp4`.

---

## 11. Rodar o app 🚀

Dê **dois cliques no `run.bat`** (ou rode no PowerShell):

```powershell
.\run.bat
```

Ele liga o Ollama, abre o navegador em **http://localhost:8765** e sobe o servidor.
Deixe a janela preta aberta enquanto usa.

Na página:

1. Cole a **URL do canal do YouTube**.
2. Escolha o vídeo/episódio.
3. Espere o pipeline (baixar → transcrever → escolher cortes → renderizar).

Os cortes saem em:

```
output\<episódio>\longos\   (16:9, 10–12 min, com thumbnail)
output\<episódio>\shorts\   (9:16, com legenda)
```

Cada corte tem `video.mp4`, `descricao.txt` e `metadata.json`.

Para **fechar tudo** (servidor + Ollama, libera a memória da GPU): dois cliques no `stop.bat`.

---

## 12. (Opcional) Upload automático para o YouTube

Siga o guia **`GOOGLE_SETUP.md`** usando a **sua** conta Google. No passo 6 dele,
salve o `client_secret.json` dentro da **sua** pasta do projeto
(`C:\Users\SEU_USUARIO\Desktop\podcast_clipper\client_secret.json`).

---

## 🧯 Problemas comuns

| Sintoma | Solução |
|---|---|
| `py` não é reconhecido | Feche e abra o PowerShell. Se continuar, reinstale o Python (passo 2). |
| "ffmpeg não encontrado" na página | Rode o passo 3 de novo e reinicie o app (`stop.bat` → `run.bat`). |
| "ollama não está rodando" | Abra o app **Ollama** pelo menu Iniciar, ou rode `ollama serve` num PowerShell separado. |
| "modelo qwen3:8b não baixado" | `ollama pull qwen3:8b` |
| Log diz "GPU indisponível, usando CPU" | Normal sem NVIDIA. Com NVIDIA: atualize o driver (passo 5). |
| Download do YouTube falha / erro 403 | Atualize o yt-dlp: `.venv\Scripts\python.exe -m pip install -U yt-dlp` |
| Porta 8765 em uso | Rode o `stop.bat` e abra de novo. |
| PC travando durante o render | Baixe `render.parallel_renders` para `1` no `config.yaml`. |
