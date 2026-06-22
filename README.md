# 🎓 ACE Results Portal

A modern, fast, and unified dashboard designed to provide ACE Engineering College students with instant access to their academic results.

## 🚀 Why this project?
The official college ERP system can be slow, clunky, and often restricts access to results tabs due to server traffic or administrative toggles. 

This portal acts as an independent, lightweight interface. By bypassing the traditional UI and interacting directly with the backend, it provides:
* **Reliability:** Check your results anytime, regardless of whether the college web-team has hidden the tab.
* **Speed:** A streamlined experience that fetches data without the bloat of the official ERP.
* **Clarity:** A structured, easy-to-read transcript layout that is fully optimized for mobile devices.

## 🛠 Tech Stack
- **Backend:** Flask (Python)
- **Data Logic:** BeautifulSoup4 & Requests (Session-managed scraping)
- **Frontend:** HTML5, CSS3, & Vanilla JavaScript
- **Visualization:** Chart.js
- **Deployment:** Vercel (Serverless)

## 📋 Key Features
- **Smart Parsing:** Dynamically adapts to different batch syllabus regulations (R21, R22, etc.).
- **Visual Analytics:** Real-time SGPA progression charts and status tracking.
- **Mobile Optimized:** Designed to be used on the go with a native-feeling experience.
- **Privacy Focused:** Your login credentials are used solely to fetch your data and are never stored on our servers.

## ⚙️ How it Works
1. **Secure Handshake:** The app initiates a secure session with the `aceexam.in` server.
2. **Data Extraction:** It triggers the specific ASP.NET postbacks needed to load your transcript.
3. **Normalization:** The HTML table is parsed dynamically, stripping away unnecessary whitespace and columns, regardless of how the college formats the table.
4. **Clean Presentation:** Data is converted to JSON and rendered into a modern, Vercel-inspired glassmorphism UI.

## 📦 Deployment
This project is built to run on **Vercel** as a serverless Python application.
1. Fork this repository.
2. Connect your GitHub to [Vercel](https://vercel.com).
3. Import the project and deploy.

---
*Made by <span>Rvind</span>*
