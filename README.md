# 🇬🇧 UK Deals Scanner

Automated UK deal-finder → scores Amazon UK price drops by quality → posts the
best to Telegram. Free to run (GitHub Actions + Supabase free tier). Built to
grow a deals audience before spending a penny.

**→ Full setup in [SETUP.md](SETUP.md).** You only ever edit `config.yaml`.

```bash
pip install -r requirements.txt
cp .env.example .env        # add your secrets
python main.py --test       # dry run: prints deals, posts nothing
```

Features: deal-quality scoring (0–100), per-category channels, automatic
affiliate tagging + disclosure, price-history tracking, optional click
tracking, failure alerts.

> Not legal/financial advice. Follow the Amazon Associates Operating Agreement.
