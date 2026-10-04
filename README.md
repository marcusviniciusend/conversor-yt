# conversor-yt

Aplicação web local, em Python + Flask, que recebe links do YouTube e devolve os arquivos
em **MP3** (áudio) ou **MP4** (vídeo), usando a biblioteca [yt-dlp](https://github.com/yt-dlp/yt-dlp)
e o **ffmpeg** para conversão e mesclagem.

A página roda apenas na sua máquina, em `http://127.0.0.1:5000`. Você cola vários links
(um por linha), escolhe o formato e acompanha a fila: item atual, percentual, sucessos,
falhas e itens pulados.

Os arquivos são salvos em `~/Music/conversor-yt` (no Windows, `C:\Users\<você>\Music\conversor-yt`),
com o título do vídeo como nome do arquivo.

## Pré-requisitos

- **Python 3.10+**
- **ffmpeg** no PATH — faz a extração do MP3 e a mesclagem do MP4
- **Deno** no PATH — o yt-dlp usa para resolver os desafios de JavaScript do YouTube

No Windows, com winget:

```powershell
winget install Python.Python.3.11
winget install Gyan.FFmpeg
winget install DenoLand.Deno
```

Depois de instalar, abra um terminal novo e confirme:

```powershell
python --version
ffmpeg -version
deno --version
```

## Instalação

```powershell
git clone https://github.com/marcusviniciusend/conversor-yt.git
cd conversor-yt

python -m venv venv
.\venv\Scripts\Activate.ps1          # Linux/macOS: source venv/bin/activate

pip install -r requirements.txt
```

## Como rodar

```powershell
python app.py
```

Abra `http://127.0.0.1:5000` no navegador. Cole os links, escolha MP3 ou MP4 e clique
em **Baixar**. Para encerrar o servidor, use `Ctrl + C` no terminal.

## Observações

- **noplaylist**: links de Mix ou de playlist baixam **somente o vídeo indicado** na URL,
  nunca a lista inteira.
- **download_archive**: cada vídeo concluído é registrado em `~/Music/conversor-yt/baixados.txt`.
  Links já baixados antes aparecem como *pulados* em vez de baixar de novo. Apague esse
  arquivo (ou a linha correspondente) se quiser baixar algo outra vez.
- **MP3**: melhor faixa de áudio disponível, convertida para MP3 na qualidade máxima
  (`preferredquality: 0`). **MP4**: melhor vídeo mp4 + melhor áudio m4a, mesclados em mp4.
- Os downloads rodam em uma thread de background; o front-end consulta `/status/<job_id>`
  a cada 800 ms. Um link com erro não interrompe os demais da fila.
- **Quando o YouTube quebrar** (erros de formato indisponível, assinatura ou
  `nsig extraction failed`), o conserto quase sempre é atualizar o yt-dlp:

  ```powershell
  pip install -U yt-dlp
  ```

  Se o erro continuar, confirme que o Deno está no PATH e tente de novo.

## Uso responsável

Este projeto foi feito para **estudo** — aprender Flask, threads, polling e a API do yt-dlp.

Baixe apenas conteúdo **seu**, em **domínio público** ou com **licença que permita** a cópia
(Creative Commons, por exemplo). Baixar material protegido por direitos autorais sem
autorização pode violar a lei de direitos autorais e os Termos de Serviço do YouTube.
A responsabilidade pelo uso é de quem roda a aplicação.
