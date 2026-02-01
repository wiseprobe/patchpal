"""GitHub API tools for PatchPal.

This demonstrates how to integrate with GitHub's REST API to fetch repository
information, search for repos, and get user details.
"""

from typing import Optional

try:
    import requests
except ImportError:
    requests = None


def search_github_repos(query: str, language: Optional[str] = None, max_results: int = 5) -> str:
    """Search GitHub repositories by keyword.

    Args:
        query: Search query (e.g., "machine learning", "web framework")
        language: Optional programming language filter (e.g., "Python", "JavaScript")
        max_results: Maximum number of results to return (default: 5)

    Returns:
        Formatted list of repositories with stars, descriptions, and URLs
    """
    if requests is None:
        return "Error: 'requests' library not installed. Install with: pip install requests"

    try:
        # Build search query
        search_query = query
        if language:
            search_query += f" language:{language}"

        url = "https://api.github.com/search/repositories"
        params = {"q": search_query, "sort": "stars", "order": "desc", "per_page": max_results}

        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            return f"Error: GitHub API request failed (HTTP {response.status_code})"

        data = response.json()
        repos = data.get("items", [])

        if not repos:
            return f"No repositories found for '{query}'"

        result = [f"Found {len(repos)} repositories for '{query}'"]
        if language:
            result[0] += f" (language: {language})"
        result.append("")

        for i, repo in enumerate(repos, 1):
            stars = repo["stargazers_count"]
            forks = repo["forks_count"]
            language_name = repo["language"] or "N/A"

            result.append(f"{i}. {repo['full_name']} ⭐ {stars:,} 🍴 {forks:,}")
            result.append(f"   Language: {language_name}")

            description = repo["description"] or "No description"
            if len(description) > 100:
                description = description[:97] + "..."
            result.append(f"   {description}")
            result.append(f"   {repo['html_url']}")
            result.append("")

        return "\n".join(result)

    except requests.exceptions.Timeout:
        return "Error: Request timed out while searching GitHub"
    except requests.exceptions.ConnectionError:
        return "Error: Could not connect to GitHub API. Check your internet connection."
    except KeyError as e:
        return f"Error: Unexpected response format from GitHub API: missing {e}"
    except Exception as e:
        return f"Error searching GitHub: {str(e)}"


def get_github_user(username: str) -> str:
    """Get information about a GitHub user.

    Args:
        username: GitHub username (e.g., "torvalds", "gvanrossum")

    Returns:
        User profile information including bio, followers, and repositories
    """
    if requests is None:
        return "Error: 'requests' library not installed. Install with: pip install requests"

    try:
        url = f"https://api.github.com/users/{username}"
        response = requests.get(url, timeout=10)

        if response.status_code == 404:
            return f"Error: GitHub user '{username}' not found"

        if response.status_code != 200:
            return f"Error: GitHub API request failed (HTTP {response.status_code})"

        user = response.json()

        result = [
            f"GitHub User: {user['login']}",
            f"Name: {user['name'] or 'N/A'}",
            f"Bio: {user['bio'] or 'No bio'}",
            "",
            "📊 Profile Stats:",
            f"  Followers: {user['followers']:,}",
            f"  Following: {user['following']:,}",
            f"  Public Repos: {user['public_repos']:,}",
            f"  Public Gists: {user['public_gists']:,}",
            "",
            "🔗 Links:",
            f"  Profile: {user['html_url']}",
        ]

        if user.get("blog"):
            result.append(f"  Website: {user['blog']}")

        if user.get("twitter_username"):
            result.append(f"  Twitter: @{user['twitter_username']}")

        if user.get("location"):
            result.append(f"  Location: {user['location']}")

        if user.get("company"):
            result.append(f"  Company: {user['company']}")

        result.append("")
        result.append(f"📅 Joined: {user['created_at'][:10]}")

        return "\n".join(result)

    except requests.exceptions.Timeout:
        return f"Error: Request timed out while fetching user '{username}'"
    except requests.exceptions.ConnectionError:
        return "Error: Could not connect to GitHub API. Check your internet connection."
    except KeyError as e:
        return f"Error: Unexpected response format from GitHub API: missing {e}"
    except Exception as e:
        return f"Error fetching GitHub user: {str(e)}"


def get_repo_info(owner: str, repo: str) -> str:
    """Get detailed information about a GitHub repository.

    Args:
        owner: Repository owner username
        repo: Repository name

    Returns:
        Detailed repository information including stats, license, and links
    """
    if requests is None:
        return "Error: 'requests' library not installed. Install with: pip install requests"

    try:
        url = f"https://api.github.com/repos/{owner}/{repo}"
        response = requests.get(url, timeout=10)

        if response.status_code == 404:
            return f"Error: Repository '{owner}/{repo}' not found"

        if response.status_code != 200:
            return f"Error: GitHub API request failed (HTTP {response.status_code})"

        repo_data = response.json()

        result = [
            f"Repository: {repo_data['full_name']}",
            f"Description: {repo_data['description'] or 'No description'}",
            "",
            "📊 Stats:",
            f"  ⭐ Stars: {repo_data['stargazers_count']:,}",
            f"  🍴 Forks: {repo_data['forks_count']:,}",
            f"  👁️  Watchers: {repo_data['watchers_count']:,}",
            f"  🐛 Open Issues: {repo_data['open_issues_count']:,}",
            "",
            "ℹ️  Info:",
            f"  Language: {repo_data['language'] or 'N/A'}",
            f"  License: {repo_data['license']['name'] if repo_data.get('license') else 'No license'}",
            f"  Default Branch: {repo_data['default_branch']}",
            f"  Size: {repo_data['size']:,} KB",
            "",
            "🔗 Links:",
            f"  URL: {repo_data['html_url']}",
        ]

        if repo_data.get("homepage"):
            result.append(f"  Homepage: {repo_data['homepage']}")

        result.append("")
        result.append(f"📅 Created: {repo_data['created_at'][:10]}")
        result.append(f"📅 Last Updated: {repo_data['updated_at'][:10]}")
        result.append(f"📅 Last Push: {repo_data['pushed_at'][:10]}")

        if repo_data.get("topics"):
            result.append("")
            result.append(f"🏷️  Topics: {', '.join(repo_data['topics'])}")

        return "\n".join(result)

    except requests.exceptions.Timeout:
        return f"Error: Request timed out while fetching repository '{owner}/{repo}'"
    except requests.exceptions.ConnectionError:
        return "Error: Could not connect to GitHub API. Check your internet connection."
    except KeyError as e:
        return f"Error: Unexpected response format from GitHub API: missing {e}"
    except Exception as e:
        return f"Error fetching repository info: {str(e)}"
