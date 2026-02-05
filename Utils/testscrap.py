import aiohttp
import asyncio
from bs4 import BeautifulSoup
import trafilatura

async def duckduckgo_search(query: str, num_results: int = 10) -> list[str]:
  search_url = "https://html.duckduckgo.com/html/"
  headers = {"User-Agent": "Mozilla/5.0"}

  async with aiohttp.ClientSession() as session:
    data = {"q": query}
    async with session.post(search_url, data=data, headers=headers) as resp:
      html = await resp.text()

  soup = BeautifulSoup(html, "html.parser")
  links = []

  for a in soup.find_all("a", class_="result__a", limit=num_results * 3):
    href = a.get("href")
    if href and href.startswith("http"):
      links.append(href)
  return links

async def scrape_page(session, url: str) -> dict | None:
  headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
  }

  try:
    async with session.get(url, headers=headers, timeout=10) as resp:
      if resp.status != 200:
        return None
      html = await resp.text()

      main_text = trafilatura.extract(html)
      if not main_text:
        return None

      trimmed = main_text.strip()[:3000]
      soup = BeautifulSoup(html, 'html.parser')
      title = soup.title.string.strip() if soup.title else "Без заголовка"

      return {
        'url': url,
        'title': title,
        'text': trimmed
      }

  except Exception:
    return None

async def scrape_n_successful(urls: list[str], n_target: int) -> list[dict]:
  results = []
  connector = aiohttp.TCPConnector(ssl=False)
  async with aiohttp.ClientSession(connector=connector) as session:
    for url in urls:
      if len(results) >= n_target:
        break
      result = await scrape_page(session, url)
      if result:
        results.append(result)
  return results

async def async_web_search_tool(query: str, count: int = 5) -> list[dict]:
  urls = await duckduckgo_search(query, count)
  if not urls:
    return []

  results = await scrape_n_successful(urls, count)
  return results

if __name__ == "__main__":
  query = "rtx 4090 kaina"
  results = asyncio.run(async_web_search_tool(query, count=5))
  for result in results:
    print(f"Title: {result['title']}")
    print(f"URL: {result['url']}")
    print(f"Text: {result['text']}...")
    print()