# Azure Student Free Tier Deployment Guide (Portal/Website Version)

This guide walks you through deploying the application **entirely through the Azure Portal Website**, with zero command-line tools required.

## Prerequisites

- An active **Azure for Students** Account ($100 credit)
- A free **GitHub** account

---

## Step 1: Upload Your Code to GitHub

Azure Web Apps can automatically pull, build, and deploy code directly from a private or public GitHub repository.

1. Go to [GitHub](https://github.com/) and create a new repository (e.g., `vision-assist-app`).
2. Upload all the files from this project (including `Dockerfile`, `requirements.txt`, and the `src/` folder) into that repository.

---

## Step 2: Get a Hugging Face API Key

Before deploying, you need a Hugging Face API key to process the images natively in the cloud for free.

1. Go to [Hugging Face](https://huggingface.co/) and create a free account if you don't have one.
2. Log in and go to your **Settings** (click your profile picture in the top right).
3. Click on **Access Tokens** on the left menu.
4. Click **New token**.
   - **Name**: Give it a descriptive name (e.g., `vision-assist-app`).
   - **Role**: `Read` is sufficient for using the Inference API.
5. Click **Generate a token** and copy the generated token. Keep it secret!

---

## Step 3: Deployment Options

Azure for Students often has strict "Resource disallowed by policy" region limits that completely block **App Services**. If you encounter this, try **Option 2** (Azure Container Apps) or **Option 3** (Render.com - Recommended).

### Option 1: Azure App Service (Original Method)

1. Go back to the [Azure Portal](https://portal.azure.com/) home screen.
2. Search for **App Services** and click it.
3. Click **+ Create** -> **Web App**.
4. Fill in the **Basics** tab:
   - **Subscription**: Azure for Students
   - **Resource Group**: Select the one you made earlier (`visionassist-rg`).
   - **Name**: A unique name (e.g., `visionassist-api-mr`). This will literally be your URL!
   - **Publish**: Choose **Docker Container**.
   - **Operating System**: **Linux**.
   - **Region**: Choose **West US 2**, **Central US**, or **Japan East**. *(Keep trying regions if you get a policy error here). [[Allowed resource deployment regions - Microsoft Azure](https://portal.azure.com/#view/Microsoft_Azure_Policy/AssignmentDetail.ReactView/id/%2Fsubscriptions%2F46886733-169e-47df-9f4b-4328b96c7745%2Fproviders%2Fmicrosoft.authorization%2Fpolicyassignments%2Fsys.regionrestriction/selectedScopes~/%5B%22%2Fsubscriptions%2F46886733-169e-47df-9f4b-4328b96c7745%22%5D)]*
   - **Pricing Plan**: Click "Explore pricing plans", select the **Free (F1)** or **Basic (B1)** tier.
5. Go to the **Docker** tab at the top:
   - **Image Source**: **Quickstart** (Leave other settings as default)
6. Click **Review + Create**, then click **Create**. Wait for deployment to finish.
7. Click **Go to resource**.
8. On the left menu of the new app, scroll down to the **Deployment** section and click **Deployment Center**.
9. Under the **Settings** tab, ignore the "sidecar containers" option (keep Continuous deployment for main container enabled). 
10. Change the **Source** dropdown from "Other container registries" to **GitHub**. Authorize it if asked.
   - **Organization**: Your GitHub Username
   - **Repository**: The repository you made in Step 1 (e.g. `vision-assist-app`)
   - **Branch**: `main` or `master`
11. Click **Save** at the top.

*If you successfully created the App Service, proceed to Step 4.*

### Option 2: Azure Container Apps (Alternative Azure Service)

If App Services are blocked in all regions, Container Apps often bypass this student limit.

1. Go back to the [Azure Portal](https://portal.azure.com/) home screen.
2. Search for **Container Apps** and click it.
3. Click **+ Create**.
4. Fill in the **Basics** tab:
   - **Subscription**: Azure for Students
   - **Resource Group**: `visionassist-rg`
   - **Container apps environment**: Click "Create new", name it `visionassist-env`, and choose available region.
5. In the **Container** tab, point to your GitHub repository and automatically create a CI/CD build.
6. Make sure to Enable **Ingress** under the App settings so the app has a public URL.

### Option 3: Render (Easiest Free Alternative) ⭐ Recommended

Since we moved to the Hugging Face API, the backend handles zero AI load itself! You don't even need Azure to host it. [Render.com](https://render.com/) offers a simpler, free continuous deployment process.

1. Go to [Render](https://render.com/) and sign up with GitHub.
2. Click **New +** and select **Web Service**.
3. Connect the `vision-assist-app` repository you created in Step 1.
4. Set the Language/Runtime to **Python**.
5. **Start Command**: `uvicorn src.backend.main:app --host 0.0.0.0 --port $PORT`
6. Click **Advanced** and add the Variables from Step 4 below!

---

## Step 4: Add Environment Variables

Your app needs the AI keys to function.

**IF you used Azure App Service (Option 1):**

1. Wait for the Web App deployment to finish, then click **Go to resource**.
2. On the left menu, under the **Settings** section, click **Environment variables**.
3. Under the **App settings** tab, click **+ Add** and add these two exact variables one by one:
   - Name: `HUGGINGFACE_API_KEY` | Value: *(Paste the Token from Step 2)*
   - Name: `HUGGINGFACE_MODEL_URL` | Value: `https://api-inference.huggingface.co/models/microsoft/git-base-coco`
4. Click **Apply** at the bottom, then click **Confirm** in the pop-up to restart the server.

**IF you used Render (Option 3):**
Add the exact same variables in the **Environment Variables** section during configuration (or later in the settings).

---

## Step 5: Update Frontend URL

Once your web host (Azure or Render) is running, it will give you a default URL on its Dashboard.

1. Open `src/frontend/app.js` locally (or in GitHub).
2. Update the API URLs at the top of the file to your new Server URL:
   ```javascript
   const API_BASE_URL = 'https://<your-app-name>.azurewebsites.net'; // Or .onrender.com
   const WS_URL = 'wss://<your-app-name>.azurewebsites.net/ws/livestream'; 
   ```
3. Since we deployed the frontend inside the same backend container for simplicity, you can just visit your Server URL in your browser, and the app will load!
