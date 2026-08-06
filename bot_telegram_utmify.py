"""
Bot Telegram para notificações de vendas via UTMify.
Recebe webhooks da UTMify e envia mensagens formatadas no Telegram.
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify
import requests

# ============================================================
# CONFIGURAÇÃO — preencha com seus dados
# ============================================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "SEU_TOKEN_AQUI")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "SEU_CHAT_ID_AQUI")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")  # opcional, para validar origem
# ============================================================

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


def enviar_telegram(mensagem: str):
    """Envia uma mensagem para o chat/grupo configurado no Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem,
        "parse_mode": "HTML",
    }
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


def formatar_valor_usd(valor) -> str:
    """Formata valor numérico para USD."""
    try:
        v = float(valor)
        if v == int(v):
            return f"US$ {int(v)}"
        return f"US$ {v:,.2f}"
    except (ValueError, TypeError):
        return str(valor)


def formatar_mensagem(dados: dict) -> str:
    """
    Monta a mensagem de notificação no estilo BuyGoods.
    """
    # Campos do webhook UTMify/BuyGoods
    comissao = dados.get("commission", dados.get("comission", dados.get("COMMISSION_AMOUNT", "")))
    pedido = dados.get("order_id", dados.get("orderId", dados.get("transaction_id",
             dados.get("transaction", dados.get("sale_id", dados.get("ORDERID", ""))))))
    campanha = dados.get("src", dados.get("sck", dados.get("utm_campaign",
               dados.get("SUBID", dados.get("subid", dados.get("campaign", ""))))))
    produto = dados.get("product_name", dados.get("prod_name", dados.get("product", "")))
    status = dados.get("status", dados.get("transaction_status", ""))

    # Montar mensagem no estilo visual
    linhas = ["🎉 <b>Nova Venda BuyGoods!</b>", ""]

    if comissao:
        linhas.append(f"💵 Comissão: {formatar_valor_usd(comissao)}")
    if pedido:
        linhas.append(f"🛒 Pedido: {pedido}")
    if campanha:
        linhas.append(f"📈 Campanha: {campanha}")
    if produto:
        linhas.append(f"📦 Produto: {produto}")
    if status:
        linhas.append(f"📋 Status: {status}")

    linhas.append("")
    linhas.append(f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

    return "\n".join(linhas)


# ============================================================
# ROTAS
# ============================================================

@app.route("/webhook", methods=["POST"])
def webhook():
    """Endpoint que recebe o POST da UTMify."""

    # Validação opcional de segredo
    if WEBHOOK_SECRET:
        token = request.headers.get("X-Webhook-Secret", request.args.get("secret", ""))
        if token != WEBHOOK_SECRET:
            return jsonify({"error": "unauthorized"}), 401

    # Aceita JSON ou form-encoded
    if request.is_json:
        dados = request.get_json(force=True)
    else:
        dados = request.form.to_dict()

    app.logger.info("Webhook recebido: %s", json.dumps(dados, ensure_ascii=False, default=str))

    try:
        mensagem = formatar_mensagem(dados)
        enviar_telegram(mensagem)
        app.logger.info("Notificação enviada com sucesso.")
        return jsonify({"ok": True}), 200
    except Exception as e:
        app.logger.error("Erro ao enviar notificação: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check — útil para monitoramento."""
    return jsonify({"status": "ok"}), 200


@app.route("/test", methods=["GET"])
def test():
    """Envia uma mensagem de teste para verificar se o bot está funcionando."""
    try:
        enviar_telegram("🧪 <b>Teste!</b>\nSeu bot de vendas está funcionando corretamente.")
        return jsonify({"ok": True, "message": "Mensagem de teste enviada!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
