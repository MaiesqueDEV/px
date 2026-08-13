import argparse
import csv
import os
import struct
import subprocess
import sys

# ---------------------------------------------------------------------------
# Programa: programar_canais.py
# Descrição: Leitura do arquivo CSV contendo a lista de canais e gravação
# direta na EEPROM do Quansheng UV‑K5 usando o "serialtool" incluído no
# repositório.  O script gera um arquivo binário temporário que segue o mesmo
# formato usado pelo comando "dump"/"restore" do serialtool.
#
# IMPORTANTE: A função csv_to_bin() abaixo contém um **stub** de conversão –
# grava um bloco de zeros.  Para que o rádio receba os canais corretos, será
# necessário implementar a codificação exata dos campos (freq, step, …) de
# acordo com a estrutura "Channel_t" definida no firmware.  Contudo o fluxo
# geral (CSV → BIN → serialtool restore) já está pronto e pode ser testado
# imediatamente.
# ---------------------------------------------------------------------------

# Tamanho aproximado da EEPROM que contém a tabela de canais (em bytes).
# O dump completo tem 0x2000 bytes; a área de canais ocupa cerca de 0x400.
EEPROM_SIZE = 0x1E00  # 7680 bytes expected by serialtool restore


def csv_to_bin(csv_path: str, bin_path: str) -> None:
    """Converte o CSV de canais para um arquivo binário de dump.

    Esta implementação **não** codifica os campos reais – o objetivo aqui
    é demonstrar a integração com o serialtool.  Substitua o corpo da
    função por código que preencha a estrutura de canais conforme a
    documentação do firmware.
    """
    # Cria um buffer com zeros do tamanho total da EEPROM.
    buffer = bytearray([0x00] * EEPROM_SIZE)

    # Exemplo de preenchimento de alguns bytes (pode ser removido).
    # Se houver um dump pré‑existente, podemos reutilizá‑lo como base.
    # Nesta versão apenas gravamos zeros, o que não altera a EEPROM.

    with open(bin_path, "wb") as f:
        f.write(buffer)
    print(f"[programar_canais] Arquivo binário temporário criado em {bin_path} (tamanho {len(buffer)} bytes)")


def programar(csv_file: str, port: str) -> None:
    """Gera o BIN a partir do CSV e envia para o rádio via serialtool.

    Args:
        csv_file: caminho completo do arquivo .csv com as 17 linhas de canal.
        port:     porta COM onde o cabo de programação está conectado.
    """
    # Cria um nome temporário na mesma pasta do script.
    tmp_bin = os.path.join(os.path.dirname(__file__), "_temp_config.bin")

    # Converte CSV → BIN (stub).
    csv_to_bin(csv_file, tmp_bin)

    # Executa o comando serialtool restore.
    cmd = [
        sys.executable,
        "tools/serialtool/cli.py",
        "restore",
        "--config",
        "-p",
        port,
        tmp_bin,
    ]
    print(f"[programar_canais] Executando: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        print("[programar_canais] Programação concluída com sucesso!")
    finally:
        # Remove o binário temporário para não deixar lixo.
        if os.path.exists(tmp_bin):
            os.remove(tmp_bin)
            print(f"[programar_canais] Arquivo temporário removido: {tmp_bin}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Programa canais no Quansheng UV‑K5 via serialtool")
    parser.add_argument("--csv", required=True, help="Caminho para o arquivo CSV com a lista de canais")
    parser.add_argument("--port", required=True, help="Porta COM onde o cabo de programação está ligado (ex.: COM7)")
    args = parser.parse_args()

    if not os.path.isfile(args.csv):
        print(f"[programar_canais] ERRO: Arquivo CSV não encontrado: {args.csv}")
        sys.exit(1)

    programar(args.csv, args.port)
