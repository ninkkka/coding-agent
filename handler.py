import os
import requests
from github import Github
import google.generativeai as genai

# 1. Configure Gemini API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

model = genai.GenerativeModel('gemini-2.0-flash-exp')

def handle_build_request(data):
    """
    This function handles the entire flow:
    1. Receives code and a description
    2. Enhances it with Gemini
    3. Deploys it to Hugging Face
    4. Returns the results
    """
    
    try:
        # 1. Extract data
        task_description = data.get('task', 'Improve the code')
        user_code = data.get('code', '')
        
        print(f"\n=== Task Received ===")
        print(f"Task: {task_description}")
        print(f"Code Length: {len(user_code)} chars")
        print(f"========================\n")

        # 2. Enhance the code with Gemini
        prompt = f"""
You are an expert software developer.

The user has provided the following task description:
{task_description}

And the following code:
```
{user_code}
```

Your job is to:
1. Fully implement or improve the code based on the task description.
2. Ensure it is production-ready, well-structured, and follows best practices.
3. Add necessary error handling, logging, and documentation.
4. Return ONLY the complete, executable code without any additional explanations or markdown code blocks.
"""

        print("Calling Gemini to enhance the code...")
        response = model.generate_content(prompt)
        enhanced_code = response.text.strip()

        print(f"Enhanced Code Length: {len(enhanced_code)} chars\n")

        # 3. Deploy to Hugging Face Spaces via GitHub API
        print("Preparing to deploy to Hugging Face...")
        
        # Initialize GitHub
        g = Github(os.getenv('GITHUB_TOKEN'))
        repo_name = "23f3004176/TDS"  # Your Hugging Face username/space
        
        try:
            repo = g.get_repo(repo_name)
            print(f"Repository found: {repo_name}")
        except Exception as e:
            print(f"Error accessing repository: {e}")
            return

        # 4. Update app.py in the repository
        file_path = "app.py"
        
        try:
            # Get the current file to obtain its SHA
            contents = repo.get_contents(file_path, ref="main")
            
            # Update the file
            repo.update_file(
                path=contents.path,
                message=f"Auto-deploy: {task_description[:50]}",
                content=enhanced_code,
                sha=contents.sha,
                branch="main"
            )
            
            print(f"Successfully updated {file_path} in {repo_name}")
            print(f"Deployment complete! 🚀")
            print(f"\nYour app should be live at: https://huggingface.co/spaces/{repo_name}")
            
        except Exception as e:
            print(f"Error updating file: {e}")
            
    except Exception as e:
        print(f"Error in handle_build_request: {e}")
