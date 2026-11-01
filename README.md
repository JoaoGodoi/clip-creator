# 🎬 Podcast Clipper

Cola o link de um canal do YouTube, escolhe o episódio e o app faz os cortes:

- **Cortes longos** (10–12 min, 16:9) com ending, título, descrição e thumbnail.
- **Shorts/Reels** (9:16) com legenda automática palavra por palavra.

Tudo roda no seu PC: download (yt-dlp), transcrição (Whisper), escolha dos melhores
trechos (IA local, Ollama) e edição (FFmpeg).

Para **Windows 10/11**. Precisa de ~18 GB livres e internet boa (baixa uns 10 GB na instalação).

---

## ✅ Instalar

1. Pegue o arquivo **`PodcastClipper-Setup.exe`** (com quem te passou o app).
2. Dê **dois cliques** nele.
   - Se aparecer "O Windows protegeu o computador": clique em **Mais informações** →
     **Executar assim mesmo**.
3. Clique em **Avançar** → **Instalar**.
4. Vai abrir uma **janela preta** baixando tudo. **Não feche.** Na primeira vez leva de
   20 min a mais de 1 hora, dependendo da internet. Quando aparecer **PRONTO!**, ela fecha sozinha.
5. Clique em **Concluir**. O app abre no navegador.

Não precisa instalar nada antes nem ser administrador: o instalador baixa sozinho Python,
FFmpeg, Ollama, o modelo de IA, as bibliotecas (com aceleração de GPU se tiver placa
NVIDIA) e os vídeos de fundo dos shorts.

**Tudo fica na pasta que você escolher no instalador**, inclusive o Ollama e o modelo de IA.
SSD pequeno? Escolha uma pasta no HD (ex.: `D:\PodcastClipper`) e o C: fica livre.

## ▶️ Usar

1. Abra o atalho **Podcast Clipper** na Área de Trabalho. O navegador abre em
   **http://localhost:8765**. Deixe a janela preta aberta enquanto usa.
2. Cole a **URL do canal do YouTube**, escolha o episódio e espere.
3. Os cortes aparecem em **Menu Iniciar → Podcast Clipper → Pasta dos cortes**:
   - `longos\`: vídeos 16:9 com thumbnail;
   - `shorts\`: vídeos 9:16 com legenda.

   Cada corte vem com `video.mp4`, `descricao.txt` e `metadata.json`.
4. Para fechar tudo: **Menu Iniciar → Fechar Podcast Clipper**.

## 🔄 Atualizar / consertar

**Menu Iniciar → Atualizar Podcast Clipper.** Baixa a versão mais nova do código, corrige
o que estiver faltando ou quebrado e testa tudo no final. Resolve a maioria dos problemas.

## 🧯 Problemas comuns

| Sintoma | Solução |
|---|---|
| Deu erro na janela preta da instalação | Mande um print + o arquivo `%LOCALAPPDATA%\PodcastClipper\install-log.txt` (cole esse caminho na barra do Explorer). |
| Download do YouTube falha / erro 403 | Feche e abra o app: ao abrir ele atualiza o yt-dlp sozinho. |
| "ollama não está rodando" | Feche (Menu Iniciar → Fechar Podcast Clipper) e abra o app de novo. |
| Log diz "GPU indisponível, usando CPU" | Normal sem placa NVIDIA. Com NVIDIA: atualize o driver em nvidia.com/pt-br/drivers. |
| PC travando no render | No `config.yaml`, coloque `render.parallel_renders: 1`. |
| Qualquer outro erro estranho | **Atualizar Podcast Clipper** no Menu Iniciar. |

## ⚙️ Personalizar (opcional)

O app fica em `%LOCALAPPDATA%\PodcastClipper\app`. Abra o `config.yaml` de lá com o Bloco de Notas:

- `podcast.nome`: nome do podcast de onde vêm os cortes (vai nos créditos).
- `whisper.model`: `medium` é o padrão. PC sem placa NVIDIA: use `small` (mais rápido).
- `cuts.long.count` / `cuts.shorts.count`: quantos cortes gerar por vídeo.
- Intro/ending dos cortes longos: coloque `assets\intro.mp4` e/ou `assets\outro.mp4`.

O `config.yaml` é mantido quando você atualiza.

**Upload automático para o YouTube:** siga o [GOOGLE_SETUP.md](GOOGLE_SETUP.md) com a **sua**
conta Google e salve o `client_secret.json` na pasta do app.

## 🗑️ Desinstalar

**Menu Iniciar → Podcast Clipper → Desinstalar** (ou Configurações do Windows → Aplicativos).
Ele pergunta se você quer **apagar tudo**:

- **Sim**: não sobra nada, nem os cortes já gerados.
- **Não**: apaga o app (inclusive o Ollama e o modelo de IA), mas guarda os cortes já gerados.

Um Ollama que você já tinha no PC antes do Podcast Clipper não é tocado: o app usa o dele, separado.

---

## 👨‍💻 Para quem mexe no código

- `installer/PodcastClipper.iss`: instalador (Inno Setup 6). Gerar o `.exe`:
  ```powershell
  & "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" installer\PodcastClipper.iss
  ```
  Sai em `installer\Output\PodcastClipper-Setup.exe`.
- O `.exe` só leva o `installer/bootstrap.ps1`. Ele baixa o código da branch `main` e roda
  o `installer/install.ps1` dela. **Mudou o processo de instalação? É só dar push.** Não
  precisa gerar outro `.exe`.
- `tools/selftest.py` roda no fim da instalação e testa o que já quebrou por versão de
  biblioteca (decodificar áudio com o PyAV, o solver do yt-dlp para o YouTube).
- Ambiente de desenvolvimento manual: `uv venv --python 3.12 --seed`, depois
  `uv pip install -r requirements.txt` (+ `requirements-gpu.txt` com NVIDIA), e FFmpeg + Ollama no PATH.
