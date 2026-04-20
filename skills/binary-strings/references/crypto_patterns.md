# Crypto Patterns Reference

Regex patterns and analysis guidance for cryptographic material found in binary strings.

## High-Confidence Patterns

### PEM / Key Material
```regex
-----BEGIN (?:RSA |EC |DSA |)?(?:PRIVATE|PUBLIC) KEY-----
-----BEGIN CERTIFICATE(?:REQUEST)?-----
-----BEGIN (?:X509 CRL|PKCS7|ENCRYPTED PRIVATE KEY)-----
```

### Common Crypto Algorithm Strings
```regex
\b(?:AES-?(?:128|192|256)|DES|3DES|TDEA|RC4|RC2|ChaCha20|Salsa20|Blowfish|Twofish|Serpent)\b
\b(?:SHA-?(?:1|2|256|384|512)|MD5|RIPEMD-?160|Whirlpool)\b
\b(?:HMAC|PBKDF2|bcrypt|scrypt|Argon2[di]?)\b
\b(?:ECDH|ECDSA|Ed25519|X25519|secp256[kr]1|P-256|P-384|P-521|curve25519)\b
\b(?:RSA-OAEP|RSA-PSS|PKCS#?1|PKCS#?7|PKCS#?11|PKCS#?12)\b
```

### Base64 Encoded Material
```regex
^[A-Za-z0-9+/]{32,}={0,2}$
```
Try decoding these — common payloads include embedded PE files, shellcode, or config blobs.

### Hex-Encoded Keys / Hashes
```regex
^[0-9a-fA-F]{32}$   # MD5 hash or 128-bit key
^[0-9a-fA-F]{40}$   # SHA-1 hash or 160-bit key
^[0-9a-fA-F]{64}$   # SHA-256 hash or 256-bit key
^[0-9a-fA-F]{128}$  # SHA-512 hash or 512-bit key
```

---

## Analysis Steps for Crypto Strings

### 1. Identify the Algorithm
```bash
grep -Ei 'AES|DES|RC4|ChaCha|RSA|ECDH|Ed25519' filtered.txt
```

### 2. Decode Base64 Candidates
```bash
grep -E '^[A-Za-z0-9+/]{32,}={0,2}$' filtered.txt | while read b; do
    decoded=$(echo "$b" | base64 -d 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo "=== $b ==="
        echo "$decoded" | xxd | head -4
        echo "$decoded" | strings -n 4
    fi
done
```

### 3. Check for Hardcoded Keys
```bash
# Fixed-length hex strings (potential raw key material)
grep -E '^[0-9a-fA-F]{32,128}$' filtered.txt
```

### 4. PEM Extraction
If you find partial PEM headers, the key body may be nearby in the binary:
```bash
# Find offset of PEM header in binary
grep -oba "BEGIN PRIVATE KEY" <binary>
# Then extract surrounding bytes
dd if=<binary> bs=1 skip=<offset> count=2000 | strings -n 4
```

---

## Red Flags in Crypto Strings

| Finding | Risk |
|---|---|
| Hardcoded AES key / IV | Symmetric encryption key extractable → decrypt traffic |
| Hardcoded RSA private key | Full key compromise |
| `ECB` mode references | Weak block cipher mode |
| `MD5` or `SHA1` for password hashing | Weak hash, rainbow table vulnerable |
| `rand()` or `srand(time())` | Weak PRNG for crypto operations |
| Blank/default IV (`\x00\x00...`) | IV reuse vulnerability |
| Symmetric key = product serial / model | Key derivation flaw |

---

## CTF-Specific Patterns

```bash
# Flag patterns
grep -Ei 'HTB\{|CTF\{|FLAG\{|picoCTF\{|DUCTF\{|.*\}' filtered.txt

# XOR key hints
grep -Ei 'xor|key|cipher|encode|decode' filtered.txt
```
