from nextcord.ext import commands
from aiohttp import web

class UpdatesLink(commands.Cog):
  def __init__(self, bot):
    self.bot:commands.Bot = bot

  async def updates_link(self,request):
    version = request.rel_url.query.get("version", "unknown")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <title>Wolium Update v-{version}</title>
  <meta name="description" content="its best bot ever">

  <!-- Facebook Meta Tags -->
  <meta property="og:url" content="https://allegedly-known-roughy.ngrok-free.app/updates">
  <meta property="og:type" content="website">
  <meta property="og:title" content="Wolium Update v-{version}">
  <meta property="og:description" content="its best bot ever">
  <meta property="og:image" content="">

  <!-- Twitter Meta Tags -->
  <meta name="twitter:card" content="summary_large_image">
  <meta property="twitter:domain" content="allegedly-known-roughy.ngrok-free.app">
  <meta property="twitter:url" content="https://allegedly-known-roughy.ngrok-free.app/updates">
  <meta name="twitter:title" content="Wolium Update v-{version}">
  <meta name="twitter:description" content="its best bot ever">
  <meta name="twitter:image" content="">
  <style>
    body {{
      font-family: Arial, sans-serif;
      margin: 0;
      padding: 20px;
      color: #000000;
      line-height: 1.6;
    }}
    .gradient-background {{
      background: linear-gradient(300deg,#0098ff,#a2e0ff,#3d93be,#246d6c,#12aba9,#39b6ef,#08affc,#001f2d,#ccf0ff);
      background-size: 540% 540%;
      animation: gradient-animation 90s ease infinite;
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      z-index: -1;
    }}
    @keyframes gradient-animation {{
      0% {{ background-position: 0% 50%; }}
      50% {{ background-position: 100% 50%; }}
      100% {{ background-position: 0% 50%; }}
    }}
    .container {{
      max-width: 800px;
      margin: 0 auto;
      background: rgba(4,110,159,0.8);
      padding: 20px;
      border-radius: 10px;
      position: relative;
      z-index: 1;
    }}
    h1, h2 {{
      color: #001f2d;
      text-shadow: 1px 1px 3px rgba(0, 0, 0, 0.2);
    }}
    p {{
      font-size: 16px;
      color: #72dcf0;
    }}
    .meta-preview {{
      margin-top: 30px;
      background: rgba(255, 255, 255, 0.1);
      padding: 15px;
      border-radius: 10px;
      color: #46daf3;
    }}
    .meta-preview img {{
      max-width: 100%;
      border-radius: 8px;
    }}
  </style>
</head>
<body>
  <div class="gradient-background"></div>
  <div class="container">
    <h1>Wolium Update v-{version}</h1>
    <p>Welcome to version <strong>{version}</strong> of Wolium! Below you can see how this update will look as a preview in Discord.</p>

    <div class="meta-preview">
      <h2>Discord Embed Preview</h2>
      <p><strong>Title:</strong> Wolium v-{version} — Update Info</p>
      <p><strong>Description:</strong> New features, bug fixes, and improvements in version {version}.</p>
      <img src="https://top.gg/api/widget/1051105900116574250.svg" alt="Preview Image">
    </div>
  </div>
</body>
</html>"""
    response = web.Response(text=html, content_type='text/html')
    response.headers['ngrok-skip-browser-warning'] = 'true'
    return response

def setup(bot:commands.Bot):
  bot.add_cog(UpdatesLink(bot))