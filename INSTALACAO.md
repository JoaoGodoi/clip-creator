# 🛠️ Instalação do Podcast Clipper

Para **Windows 10/11**. Precisa de ~15 GB livres e internet boa (baixa uns 10 GB).

---

## ✅ Jeito fácil (recomendado)

### 1. Baixar o projeto

1. Abra **https://github.com/JoaoGodoi/clip-creator**
2. Clique no botão verde **`<> Code`** → **Download ZIP**.
3. Vá em **Downloads**, clique com o botão direito no `clip-creator-main.zip` →
   **Extrair tudo…** → escolha a **Área de Trabalho** → Extrair.

### 2. Rodar o instalador

1. Abra a pasta `clip-creator-main` que apareceu na Área de Trabalho.
2. Dê **dois cliques no `setup.bat`**.
   - Se o Windows mostrar "O Windows protegeu o computador", clique em
     **Mais informações** → **Executar assim mesmo**.
   - Se aparecer uma janela pedindo permissão de administrador, clique em **Sim**.
3. **Espere.** Pode levar de 20 min a mais de 1 hora, dependendo da internet. Não feche a janela
   até aparecer **PRONTO!** em verde.

O instalador faz tudo sozinho:

- instala o Python 3.12, o FFmpeg, o Deno e o Ollama;
- baixa o modelo de IA (`qwen3:8b`, ~5 GB);
- instala as bibliotecas do projeto (com aceleração da GPU, se tiver placa NVIDIA);
- baixa os vídeos de fundo dos shorts e a música;
- cria o atalho **Podcast Clipper** na Área de Trabalho.

> Deu erro vermelho? Rode o `setup.bat` de novo. Ele pula o que já foi feito e
> tenta só o que faltou. Se continuar dando erro, tire um print e mande.

### 3. Usar

1. Dois cliques no atalho **Podcast Clipper** da Área de Trabalho.
   O navegador abre em **http://localhost:8765**. Deixe a janela preta aberta.
2. Cole a **URL do canal do YouTube** → escolha o episódio → espere.
3. Os cortes ficam na pasta do projeto, em `output\<episódio>\`:
   - `longos\`: vídeos 16:9 de 10–12 min, com thumbnail;
   - `shorts\`: vídeos 9:16 com legenda.

   Cada corte vem com `video.mp4`, `descricao.txt` e `metadata.json`.
4. Para fechar tudo: dois cliques no **`stop.bat`** da pasta do projeto.

---

## ⚙️ Personalizar (opcional)

Abra o `config.yaml` com o Bloco de Notas:

- `podcast.nome`: nome do podcast de onde vêm os cortes (vai nos créditos).
- `whisper.model`: `medium` é o padrão. PC sem placa NVIDIA: use `small` (mais rápido).
- `cuts.long.count` / `cuts.shorts.count`: quantos cortes gerar por vídeo.
- `render.parallel_renders`: se o PC travar durante o render, coloque `1`.
- Intro/ending dos cortes longos: coloque `assets\intro.mp4` e/ou `assets\outro.mp4`.

**Upload automático para o YouTube:** siga o `GOOGLE_SETUP.md` com a **sua** conta
Google e salve o `client_secret.json` dentro da pasta do projeto.

---

## 🧯 Problemas comuns

| Sintoma | Solução |
|---|---|
| "ffmpeg não encontrado" na página | Rode o `setup.bat` de novo e reabra o app (`stop.bat` → atalho). |
| "ollama não está rodando" | Abra o app **Ollama** pelo menu Iniciar e recarregue a página. |
| Log diz "GPU indisponível, usando CPU" | Normal sem placa NVIDIA. Com NVIDIA: atualize o driver em nvidia.com/pt-br/drivers. |
| Download do YouTube falha / erro 403 | No PowerShell, dentro da pasta do projeto: `.venv\Scripts\python.exe -m pip install -U yt-dlp` |
| Porta 8765 em uso | Rode o `stop.bat` e abra de novo. |
| PC travando no render | `render.parallel_renders: 1` no `config.yaml`. |

---

## 🔧 Instalação manual (só se o `setup.bat` não funcionar)

No **PowerShell**, um comando por vez. Feche e reabra o PowerShell depois de cada `winget install`.

```powershell
winget install -e --id Python.Python.3.12
```

```powershell
winget install -e --id Gyan.FFmpeg
```

```powershell
winget install -e --id DenoLand.Deno
```

```powershell
winget install -e --id Ollama.Ollama
```

```powershell
ollama pull qwen3:8b
```

Entre na pasta do projeto (ajuste o caminho se for diferente):

```powershell
cd "$env:USERPROFILE\Desktop\clip-creator-main"
```

```powershell
py -3.12 -m venv .venv
```

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Só se tiver placa NVIDIA:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-gpu.txt
```

Os vídeos de fundo e a música são opcionais. Os links estão em `assets\*\FONTES.md`.
Exemplo de download:

```powershell
.venv\Scripts\python.exe -m yt_dlp -f "bv*[height<=1080][ext=mp4]" -o "assets\dopamine\subway_surfers.mp4" "https://www.youtube.com/watch?v=i0M4ARe9v0Y"
```

Depois é só abrir o `run.bat`.
