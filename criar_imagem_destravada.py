import sys
import os

# Script para patch de imagens do CHIRP para Quansheng UV-K5 (F4HWN / Custom)
# Substitui a string de versão por "v2.01.26" para destravar o CHIRP e remover o Read-Only!

def patch_chirp_img(file_path):
    if not os.path.exists(file_path):
        print(f"Arquivo {file_path} nao encontrado!")
        return

    with open(file_path, "rb") as f:
        data = bytearray(f.read())

    # Endereço da versão na EEPROM do UV-K5 (0x1EC0 - 0x1ED0)
    version_offset = 0x1EC0
    stock_version = b"v2.01.26\x00\x00\x00\x00\x00\x00\x00\x00"

    if len(data) >= (version_offset + len(stock_version)):
        data[version_offset:version_offset+len(stock_version)] = stock_version

    out_file = file_path.replace(".img", "_DESTRAVADO.img")
    with open(out_file, "wb") as f:
        f.write(data)

    print(f"Sucesso! Arquivo destravado criado em: {out_file}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        patch_chirp_img(sys.argv[1])
    else:
        # Procurar qualquer .img na pasta
        files = [f for f in os.listdir(".") if f.endswith(".img")]
        for f in files:
            patch_chirp_img(f)
