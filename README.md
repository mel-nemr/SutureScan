# SutureScan

An open-source, 100% offline AI tool designed for global health initiatives, medical outreach trips, and disaster relief teams.

This project allows volunteers to use their mobile phones to rapidly scan medical supplies (like sutures), extract critical data (Brand, Material, Size, Expiry Date) using a local AI model, and automatically compile everything into an Excel spreadsheet.

✨ Key Features

100% Offline: Runs entirely on a local laptop and mobile phone via a local Wi-Fi network or hotspot. No internet connection required after initial setup.

Zero Cost: Uses open-source AI models (e.g., Gemma, Qwen). No API keys or pay-per-scan fees.

High-Speed Batching: Custom-built interface allows continuous scanning.

Smart Error Correction: Automatically prompts the user to rescan if the AI misses critical data like the expiry date, ensuring a clean and accurate catalogue.

Privacy First: No data or inventory lists are sent to the cloud.

🛠️ Prerequisites

Before heading out on your outreach trip, you will need to set this up on a central laptop.

A Laptop: Preferably with a dedicated GPU (MacBook M-series or Windows/Linux with NVIDIA), though modern CPUs will also work at a slightly slower speed.

A Smartphone: iOS (Safari) or Android (Chrome) to act as the scanner.

Python 3.10+ installed on the laptop.

LM Studio installed on the laptop (for running the AI locally).

🚀 Setup Guide

Step 1: Install and Configure LM Studio

This programme runs the AI model on your laptop.

Download and install LM Studio.

Open LM Studio and search for Gemma or Qwen or any other preferred model (we recommend a 4B or 9B parameter instruct/base model for the best balance of speed and accuracy). Download it.

Go to the Local Server tab (the < > icon on the left).

Select your downloaded model at the top.

Click Start Server. (Ensure it is running on http://localhost:1234/v1).

Step 2: Download This Project

Clone this repository to your laptop, or simply download it as a ZIP file and extract it.


Step 3: Install Dependencies

Open your terminal or command prompt in the project folder and install the required Python packages:

pip install -r requirements.txt


(Note: You will need to create a requirements.txt file containing fastapi, uvicorn, pandas, openpyxl, Pillow, openai, and python-multipart)

Step 4: Generate SSL Certificates (Crucial for Mobile Cameras)

Mobile browsers require a secure connection (HTTPS) to access the camera. Generate local certificates by running this command in your terminal:

# On Mac/Linux
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365

# On Windows (using Git Bash or OpenSSL)
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365


Just press Enter through all the prompts it gives you.

📱 How to Use During the Outreach Trip

1. Start the Server

Ensure your laptop and your mobile phone are connected to the same Wi-Fi network (or connect your phone to your laptop's mobile hotspot).

Run the server using Uvicorn:

uvicorn main:app --host 0.0.0.0 --port 8000 --ssl-keyfile key.pem --ssl-certfile cert.pem


2. Find Your Laptop's Local IP Address

Mac: Go to System Settings > Network > Wi-Fi > Details (Look for IP Address, e.g., 192.168.1.5).

Windows: Open Command Prompt and type ipconfig (Look for IPv4 Address).

3. Connect Your Phone

Open Safari or Chrome on your phone.

Type in https://[YOUR_IP_ADDRESS]:8000 (e.g., https://192.168.1.5:8000).

Security Warning: Your browser will warn you that the connection is "Not Private" (because we created our own SSL certificates). Click Advanced and then Proceed/Continue.

Grant the website permission to use your camera.

4. Start Scanning!

Frame the medical package in the yellow box.

Ensure the Expiry Date (hourglass symbol) is in focus.

Tap Capture Suture.

The server will analyse the image and log it in the suture_catalogue.xlsx file on your laptop. If it misses data, a prompt will appear on your phone asking you to rescan.

💡 Top Tips for Scanning

Glare is the enemy: Glossy sterile packaging reflects light. Angle your phone slightly to avoid overhead light reflecting directly into the camera lens.

Focus on the symbols: The AI is specifically trained to hunt for the hourglass symbol (ISO 7000-2607) and thread gauge size. Keep these clear and central.

🤝 Contributing

Contributions from the medical and developer communities are highly encouraged! Feel free to submit Pull Requests to improve the interface, optimise prompts, or add support for different types of medical supplies (e.g., surgical staples, catheters).

📄 License

This project is open-source and available under the MIT License.
