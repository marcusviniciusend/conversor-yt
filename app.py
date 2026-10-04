"""conversor-yt — aplicação web local para baixar áudio ou vídeo do YouTube."""

from __future__ import annotations

import copy
import re
import threading
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

PASTA_SAIDA = Path.home() / "Music" / "conversor-yt"
ARQUIVO_ARCHIVE = PASTA_SAIDA / "baixados.txt"
FORMATOS = ("mp3", "mp4")
ANSI = re.compile(r"\x1b\[[0-9;]*m")

app = Flask(__name__)

_tarefas: dict[str, dict] = {}
_trava = threading.Lock()


def _atualiza(job_id: str, **campos) -> None:
    with _trava:
        tarefa = _tarefas.get(job_id)
        if tarefa is not None:
            tarefa.update(campos)


def _atualiza_item(job_id: str, indice: int, **campos) -> None:
    with _trava:
        tarefa = _tarefas.get(job_id)
        if tarefa is not None:
            tarefa["itens"][indice].update(campos)


def _soma(job_id: str, chave: str) -> None:
    with _trava:
        tarefa = _tarefas.get(job_id)
        if tarefa is not None:
            tarefa[chave] += 1


def _opcoes_ydl(formato: str, hook) -> dict:
    """Opções do yt-dlp: um vídeo por link, archive ligado, melhor qualidade."""
    opcoes = {
        "outtmpl": str(PASTA_SAIDA / "%(title)s.%(ext)s"),
        "noplaylist": True,
        "download_archive": str(ARQUIVO_ARCHIVE),
        "progress_hooks": [hook],
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "retries": 3,
        "windowsfilenames": True,
    }
    if formato == "mp3":
        opcoes.update(
            {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "0",
                    }
                ],
            }
        )
    else:
        opcoes.update(
            {
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
            }
        )
    return opcoes


def _video_unico(info: dict | None) -> dict:
    """Com noplaylist um link de Mix ainda pode voltar como playlist; pega o primeiro."""
    if not info:
        raise DownloadError("O yt-dlp não encontrou nenhum vídeo nesse link.")
    if info.get("_type") == "playlist":
        entradas = [e for e in (info.get("entries") or []) if e]
        if not entradas:
            raise DownloadError("A playlist não trouxe nenhum vídeo.")
        return entradas[0]
    return info


def _limpa_erro(texto: str) -> str:
    texto = ANSI.sub("", texto).strip()
    for prefixo in ("ERROR: ", "ERROR:"):
        if texto.startswith(prefixo):
            texto = texto[len(prefixo) :].strip()
    linha = texto.splitlines()[0] if texto else "Falha desconhecida."
    return linha[:300]


def _processa(job_id: str, links: list[str], formato: str) -> None:
    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)

    for indice, link in enumerate(links):
        _atualiza(job_id, atual=indice + 1)
        _atualiza_item(job_id, indice, estado="baixando", percentual=0, mensagem="")

        def hook(d, indice=indice):
            situacao = d.get("status")
            if situacao == "downloading":
                baixado = d.get("downloaded_bytes") or 0
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                if total:
                    pct = max(0, min(100, int(baixado * 100 / total)))
                    _atualiza_item(job_id, indice, percentual=pct)
            elif situacao == "finished":
                _atualiza_item(
                    job_id, indice, percentual=100, mensagem="Convertendo com ffmpeg"
                )

        try:
            with YoutubeDL(_opcoes_ydl(formato, hook)) as ydl:
                info = _video_unico(ydl.extract_info(link, download=False))
                _atualiza_item(job_id, indice, titulo=info.get("title") or link)

                if ydl.in_download_archive(info):
                    _atualiza_item(
                        job_id,
                        indice,
                        estado="pulado",
                        percentual=100,
                        mensagem="Já estava na lista de baixados",
                    )
                    _soma(job_id, "pulados")
                    continue

                ydl.download([link])
        except Exception as erro:  # noqa: BLE001 — um link ruim não derruba a fila
            _atualiza_item(
                job_id,
                indice,
                estado="erro",
                percentual=0,
                mensagem=_limpa_erro(str(erro)),
            )
            _soma(job_id, "falhas")
        else:
            _atualiza_item(
                job_id,
                indice,
                estado="ok",
                percentual=100,
                mensagem=f"Salvo em {PASTA_SAIDA}",
            )
            _soma(job_id, "sucessos")

    _atualiza(job_id, estado="concluido")


@app.get("/")
def pagina():
    return render_template("index.html", pasta=str(PASTA_SAIDA))


@app.post("/baixar")
def baixar():
    dados = request.get_json(silent=True) or {}
    bruto = (dados.get("links") or "").strip()
    formato = (dados.get("formato") or "").lower()

    if not bruto:
        return jsonify(erro="Cole pelo menos um link do YouTube para começar."), 400
    if formato not in FORMATOS:
        return jsonify(erro="Escolha MP3 ou MP4 antes de baixar."), 400

    links: list[str] = []
    vistos: set[str] = set()
    for linha in bruto.splitlines():
        linha = linha.strip()
        if linha and linha not in vistos:
            vistos.add(linha)
            links.append(linha)

    if not links:
        return jsonify(erro="Cole pelo menos um link do YouTube para começar."), 400

    invalidos = [l for l in links if not l.lower().startswith(("http://", "https://"))]
    if invalidos:
        lista = ", ".join(invalidos[:3]) + ("…" if len(invalidos) > 3 else "")
        return jsonify(erro=f"Estas linhas não são endereços válidos: {lista}"), 400

    job_id = uuid.uuid4().hex
    with _trava:
        _tarefas[job_id] = {
            "estado": "rodando",
            "formato": formato,
            "atual": 0,
            "total": len(links),
            "sucessos": 0,
            "falhas": 0,
            "pulados": 0,
            "pasta": str(PASTA_SAIDA),
            "itens": [
                {
                    "link": link,
                    "titulo": link,
                    "estado": "pendente",
                    "percentual": 0,
                    "mensagem": "",
                }
                for link in links
            ],
        }

    threading.Thread(target=_processa, args=(job_id, links, formato), daemon=True).start()
    return jsonify(job_id=job_id, total=len(links))


@app.get("/status/<job_id>")
def status(job_id: str):
    with _trava:
        tarefa = _tarefas.get(job_id)
        if tarefa is None:
            return jsonify(erro="Essa fila não existe mais. Envie os links de novo."), 404
        return jsonify(copy.deepcopy(tarefa))


if __name__ == "__main__":
    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
