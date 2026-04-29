# Pushing to GitHub

## First-time setup

### 1. Install Git (if you don't already have it)

Download from [git-scm.com/download/win](https://git-scm.com/download/win) and run the installer with default options.

### 2. Configure Git (one time, globally)

Open PowerShell or Git Bash and run:

```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### 3. Create a GitHub account

At [github.com](https://github.com) if you don't have one already.

## Creating and pushing the repo

### Option A: GitHub website first (easier)

1. Go to [github.com/new](https://github.com/new)
2. Name it: `ascii-video-filter` (or whatever you prefer)
3. Add a description: "GPU-accelerated video to ASCII art converter"
4. Keep it **Public** (or Private if you prefer)
5. **Don't** tick "Add a README" — you already have one
6. Click **Create repository**
7. Copy the URL GitHub shows you, e.g. `https://github.com/ryley/ascii-video-filter.git`

Then open PowerShell and run, from the project folder:

```bash
cd C:\path\to\ascii-video-filter

git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/MuscularCrab/ascii-video-filter.git
git push -u origin main
```

The first `git push` will prompt you to log in. If you don't have one, GitHub will ask for a personal access token instead of your password — create one at [github.com/settings/tokens](https://github.com/settings/tokens) (classic token, with `repo` scope is enough).

### Option B: GitHub CLI (slicker)

Install GitHub CLI from [cli.github.com](https://cli.github.com), then:

```bash
cd C:\path\to\ascii-video-filter

gh auth login
git init
git add .
git commit -m "Initial commit"
gh repo create ascii-video-filter --public --source=. --push
```

Done. It creates the repo and pushes in one step.

## Future updates

After the first push, any changes:

```bash
git add .
git commit -m "Describe what changed"
git push
```

## Recommended next steps for the repo

1. **Add screenshots** to a `docs/` folder and reference them in the README
2. **Create a GitHub Release** for major versions (makes .exe downloads easier if you build one)
3. **Update the README** with your actual GitHub username everywhere it says `MuscularCrab`
4. **Add a topic/tag** on the repo page: `ascii-art`, `video-processing`, `cuda`, `gpu`, etc. so people can find it

## Publishing a prebuilt .exe

Building a Windows .exe with CuPy bundled is tricky because CUDA runtime libraries are huge and licensed separately. If you want to distribute it anyway:

1. Build locally with `build_exe.bat`
2. Zip up `dist/AsciiVideo.exe` with a `README.txt` noting CUDA Toolkit is still required on the end user's machine
3. Go to your repo → **Releases** → **Create a new release**
4. Upload the zip as a release asset

Keep in mind the .exe won't work on machines without an NVIDIA GPU or CUDA Toolkit.
