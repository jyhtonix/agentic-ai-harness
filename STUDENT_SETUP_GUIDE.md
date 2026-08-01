\# AI Agentic Harness - Student Setup Guide (Windows)



\## 1. Introduction



This guide explains how to download, install, configure, and run the \*\*AI Agentic Harness\*\* for the first time.



The AI Agentic Harness is a cybersecurity AI framework that supports:



\* Multi-agent AI workflow

\* CTF challenge analysis

\* Security skill execution

\* Benchmark testing

\* Automated security investigation



This guide is written for students who are setting up the project on a new Windows machine.



\---



\# 2. Required Software Installation



Before downloading the repository, install the following software.



\## 2.1 Git



Download Git:



https://git-scm.com/downloads



Verify installation:



```powershell

git --version

```



Expected output:



```text

git version 2.x.x

```



\---



\## 2.2 Python



Recommended version:



```text

Python 3.12.x

```



Download:



https://www.python.org/downloads/



During installation:



Enable:



```text

Add Python.exe to PATH

```



Verify:



```powershell

python --version

```



Expected:



```text

Python 3.12.x

```



\---



\# 3. Download the Repository



Choose a suitable folder.



Example:



```text

C:\\Projects

```



Open PowerShell:



```powershell

cd C:\\Projects

```



Clone the repository:



```powershell

git clone https://github.com/jyhtonix/agentic-ai-harness.git

```



Enter the project directory:



```powershell

cd agentic-ai-harness

```



Verify the project files:



```powershell

dir

```



Expected folders:



```text

agents/

api/

core/

models/

skills\_engine/

tools/

requirements.txt

README.md

```



\---



\# 4. Important: Always Run from Project Root



All commands must be executed from:



```text

agentic-ai-harness

```



Example:



```text

C:\\Projects\\agentic-ai-harness

```



Do NOT run:



```powershell

cd api

python main.py

```



because Python may not be able to locate project modules:



```text

models/

agents/

core/

tools/

```



Correct approach:



```powershell

python -m api.main

```



\---



\# 5. Create Python Virtual Environment



From the project root:



```powershell

python -m venv .venv

```



Activate the virtual environment:



```powershell

.venv\\Scripts\\activate

```



After activation, PowerShell should show:



```text

(.venv)

```



Example:



```text

(.venv) PS C:\\Projects\\agentic-ai-harness>

```



\---



\# 6. Install Required Python Packages



Upgrade pip:



```powershell

pip install --upgrade pip

```



Install dependencies:



```powershell

pip install -r requirements.txt

```



Wait until installation is completed successfully.



\---



\# 7. Verify Project Modules



Check the `models` package:



```powershell

dir models

```



Expected files:



```text

models/



\_\_init\_\_.py

llm.py

embeddings.py

claude.yaml

deepseek\_v4\_flash.yaml

grok.yaml

kimi.yaml

```



The `models` package is required by:



```python

from models.llm import OpenAILLM

```



\---



\# 8. Configure Environment Variables



Create your local environment file:



```powershell

copy .env.example .env

```



Open:



```text

.env

```



Configure required API keys.



Example:



```env

OPENAI\_API\_KEY=your\_key\_here

DEEPSEEK\_API\_KEY=your\_key\_here

```



Important:



Do not upload `.env` files to GitHub.



\---



\# 9. Test Python Import



From the project root:



Start Python:



```powershell

python

```



Test:



```python

from models.llm import OpenAILLM

```



If no error appears, the environment is configured correctly.



Exit Python:



```python

exit()

```



\---



\# 10. Start AI Agentic Harness



From:



```text

agentic-ai-harness

```



Run:



```powershell

python -m api.main

```



Do not run:



```powershell

python api/main.py

```



\---



\# 11. Working with CTF Challenges



The repository contains cybersecurity challenges:



```text

challenges/



challenge01\_hidden\_message

challenge02\_pcap\_analysis

challenge03\_binary\_reverse

...

challenge12\_web\_liveArt

```



Each challenge contains:



\* Challenge description

\* Supporting files

\* Security artefacts

\* Analysis materials



The AI Agentic Harness can be used to analyse these challenges.



\---



\# 12. Common Errors and Solutions



\## Error 1



```

ModuleNotFoundError: No module named 'models'

```



Cause:



The application was started from the wrong directory.



Incorrect:



```powershell

cd api

python main.py

```



Correct:



```powershell

cd agentic-ai-harness

python -m api.main

```



\---



\## Error 2



```

ModuleNotFoundError: No module named xxx

```



Solution:



Activate the virtual environment:



```powershell

.venv\\Scripts\\activate

```



Install dependencies:



```powershell

pip install -r requirements.txt

```



\---



\## Error 3



Permission or file locking problems



If the project is stored inside:



```text

OneDrive\\Desktop

```



some files may be locked during synchronization.



Recommended location:



```text

C:\\Projects\\agentic-ai-harness

```



\---



\# 13. Daily Startup Procedure



After the first successful setup, use:



```powershell

cd C:\\Projects\\agentic-ai-harness



.venv\\Scripts\\activate



python -m api.main

```



\---



\# 14. Recommended Development Practice



Students are encouraged to:



\* Create their own Git branch

\* Avoid modifying core framework files without discussion

\* Keep API keys private

\* Document changes clearly

\* Use the provided CTF challenges for learning



Example branch:



```powershell

git checkout -b student-feature-name

```



\---



\# 15. Support Checklist



Before reporting an issue, check:



☐ Python installed correctly

☐ Git installed correctly

☐ Virtual environment activated

☐ Dependencies installed

☐ Running from project root

☐ `.env` configured correctly

☐ Required modules exist



\---



\## End of Setup Guide



The AI Agentic Harness is now ready for cybersecurity experimentation, CTF learning, and AI-driven security research.



