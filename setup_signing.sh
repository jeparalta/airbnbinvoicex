#!/bin/bash
set -e

echo ""
echo "=================================================="
echo "  AirbnbInvoiceX — Mac Signing Setup"
echo "=================================================="
echo ""

# ── 1. Find Developer ID certificate ──────────────────
echo "🔍 Szukam certyfikatu Developer ID Application..."
CERT_LINE=$(security find-identity -v -p codesigning | grep "Developer ID Application" | head -1)
if [ -z "$CERT_LINE" ]; then
  echo "❌ Nie znaleziono certyfikatu 'Developer ID Application' w Keychain."
  echo "   Zainstaluj go z developer.apple.com/account → Certificates."
  exit 1
fi
CERT_NAME=$(echo "$CERT_LINE" | sed -E 's/.*"(.+)".*/\1/')
echo "✅ Znaleziono: $CERT_NAME"
echo ""

# ── 2. Export .p12 ─────────────────────────────────────
echo "📦 Eksportuję certyfikat do .p12..."
echo "   Podaj hasło do eksportu (zapamiętaj je — będzie potrzebne):"
read -s CERT_PWD
echo ""
CERT_FILE="/tmp/airbnbinvoicex_cert.p12"
security export -k login.keychain -t identities -f pkcs12 \
  -o "$CERT_FILE" -P "$CERT_PWD" \
  -c "$CERT_NAME" 2>/dev/null || \
security export -k ~/Library/Keychains/login.keychain-db -t identities -f pkcs12 \
  -o "$CERT_FILE" -P "$CERT_PWD" \
  -c "$CERT_NAME"
CERT_B64=$(base64 -i "$CERT_FILE")
rm "$CERT_FILE"
echo "✅ Certyfikat wyeksportowany"
echo ""

# ── 3. Apple ID ────────────────────────────────────────
echo "📧 Podaj swój Apple ID (email):"
read APPLE_ID
echo ""

# ── 4. App-specific password ───────────────────────────
echo "🔑 Podaj App-Specific Password (wygeneruj na appleid.apple.com):"
echo "   appleid.apple.com → Sign-In and Security → App-Specific Passwords"
read -s APPLE_PWD
echo ""

# ── 5. Team ID ─────────────────────────────────────────
echo "🏢 Podaj Team ID (developer.apple.com/account → Membership):"
read TEAM_ID
echo ""

# ── 6. Add secrets to GitHub ──────────────────────────
REPO="sienioApius/airbnbinvoicex"
echo "☁️  Dodaję sekrety do GitHub..."
gh secret set MACOS_CERTIFICATE      --repo "$REPO" --body "$CERT_B64"
gh secret set MACOS_CERTIFICATE_PWD  --repo "$REPO" --body "$CERT_PWD"
gh secret set APPLE_ID               --repo "$REPO" --body "$APPLE_ID"
gh secret set APPLE_ID_PASSWORD      --repo "$REPO" --body "$APPLE_PWD"
gh secret set APPLE_TEAM_ID          --repo "$REPO" --body "$TEAM_ID"

echo ""
echo "✅ Wszystkie sekrety dodane do GitHub!"
echo ""
echo "=================================================="
echo "  Gotowe. Uruchom teraz:"
echo "  cd ~/1VIBE/airbnbinvoicex && git tag vX.X.X && git push origin vX.X.X"
echo "=================================================="
