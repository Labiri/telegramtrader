# PineConnector Telegram Bot
PineConnector Telegram Bot is a utility that integrates with PineConnector, allowing users to send trading signals directly from Telegram.

## Purpose
This bot enables users to manage and send trading signals based on their API keys. Through a simple and interactive interface, users can add, manage, and select presets of their API keys, and send trading signals based on certain parameters, such as trade side, symbol, risk, stop price, take profit, and comments.

At the moment no other commands are available, but can be easily added.

## Main Features
* Manage API Key Presets: Users can add multiple API key presets and give them friendly names for easier access.
* Send Trading Signals: With the integration of PineConnector, users can send trading signals directly through the bot.
* Interactive Menu: An interactive Telegram menu makes it easy for users to navigate and choose desired actions.
* Deployment on Heroku

## Instructions
1. Fork and clone this repository.
2. Set up a new app on Heroku.
3. Configure environment variables (TELEGRAM_TOKEN and DATABASE_URL) in Heroku settings.
4. Deploy the bot to Heroku using the Heroku Git CLI or connect your GitHub repository to auto-deploy.
5 .Ensure your PostgreSQL database (linked through DATABASE_URL) is set up with the appropriate schema.
6. Expanding the Bot

This bot serves as a base and can be expanded and adapted to other functionalities of PineConnector or even other integrations. The modular design ensures anyone can easily add more commands, integrate more features, or customize the bot as per their requirements.

## Credits
This bot is built using the Python Telegram Bot API and is designed to work with PineConnector. It is hosted and deployed using Heroku.
