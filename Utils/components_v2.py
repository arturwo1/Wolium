from nextcord import http

class BaseComp:
  def __init__(self, c_type, **kwargs):
    self.payload = {"type": c_type}
    for k, v in kwargs.items():
      if v is not None:
        self.payload[k] = v

  def to_dict(self):
    return self.payload

  def _check_len(self, val, max_l, field):
    if val is not None and len(str(val)) > max_l:
      raise ValueError(f"{field} > {max_l} chars")

  def _check_range(self, val, min_v, max_v, field):
    if val is not None and not (min_v <= val <= max_v):
      raise ValueError(f"{field} must be {min_v}-{max_v}")

class Container(BaseComp):
  def __init__(self, accent_color=None, spoiler=None):
    super().__init__(17, accent_color=accent_color, spoiler=spoiler)
    self.payload["components"] = []

  def add(self, *components):
    for c in components:
      self.payload["components"].append(c.to_dict())
    return self

class ActionRow(BaseComp):
  def __init__(self):
    super().__init__(1)
    self.payload["components"] = []

  def add(self, *components):
    if len(self.payload["components"]) + len(components) > 5:
      raise ValueError("ActionRow max 5 components")
    for c in components:
      self.payload["components"].append(c.to_dict())
    return self

class Section(BaseComp):
  def __init__(self, accessory=None):
    super().__init__(9)
    self.payload["components"] = []
    if accessory:
      self.payload["accessory"] = accessory.to_dict()

  def add(self, *components):
    if len(self.payload["components"]) + len(components) > 3:
      raise ValueError("Section max 3 components")
    for c in components:
      self.payload["components"].append(c.to_dict())
    return self

class Label(BaseComp):
  def __init__(self, label, description=None, component=None):
    super().__init__(18, label=label, description=description)
    self._check_len(label, 45, "Label label")
    self._check_len(description, 100, "Label description")
    if component:
      self.payload["component"] = component.to_dict()

class TextDisplay(BaseComp):
  def __init__(self, content):
    super().__init__(10, content=content)

class Separator(BaseComp):
  def __init__(self, spacing=1, divider=True):
    super().__init__(14, spacing=spacing, divider=divider)

class Button(BaseComp):
  def __init__(self, style, custom_id=None, label=None, emoji=None, url=None, sku_id=None, disabled=None):
    super().__init__(2, style=style, custom_id=custom_id, label=label, url=url, sku_id=sku_id, disabled=disabled)
    self._check_len(label, 80, "Button label")
    self._check_len(custom_id, 100, "Button custom_id")
    self._check_len(url, 512, "Button url")
    if emoji:
      self.payload["emoji"] = emoji

class Select(BaseComp):
  def __init__(self, c_type, custom_id, placeholder=None, min_values=None, max_values=None, disabled=None, options=None, channel_types=None, default_values=None):
    super().__init__(c_type, custom_id=custom_id, placeholder=placeholder, min_values=min_values, max_values=max_values, disabled=disabled, channel_types=channel_types)
    self._check_len(custom_id, 100, "Select custom_id")
    self._check_len(placeholder, 150, "Select placeholder")
    self._check_range(min_values, 0, 25, "Select min_values")
    self._check_range(max_values, 1, 25, "Select max_values")
    if options:
      if len(options) > 25:
        raise ValueError("Select options max 25")
      for opt in options:
        self._check_len(opt.get("label"), 100, "Option label")
        self._check_len(opt.get("value"), 100, "Option value")
        self._check_len(opt.get("description"), 100, "Option description")
      self.payload["options"] = options
    if default_values:
      self.payload["default_values"] = default_values

class TextInput(BaseComp):
  def __init__(self, custom_id, style, min_length=None, max_length=None, required=None, value=None, placeholder=None):
    super().__init__(4, custom_id=custom_id, style=style, min_length=min_length, max_length=max_length, required=required, value=value, placeholder=placeholder)
    self._check_len(custom_id, 100, "TextInput custom_id")
    self._check_len(value, 4000, "TextInput value")
    self._check_len(placeholder, 100, "TextInput placeholder")
    self._check_range(min_length, 0, 4000, "TextInput min_length")
    self._check_range(max_length, 1, 4000, "TextInput max_length")

class Thumbnail(BaseComp):
  def __init__(self, url, description=None, spoiler=None):
    media = {"url": url}
    if description:
      self._check_len(description, 1024, "Thumbnail description")
      media["description"] = description
    if spoiler:
      media["spoiler"] = spoiler
    super().__init__(11, media=media)

class MediaGallery(BaseComp):
  def __init__(self, items):
    if len(items) > 10:
      raise ValueError("MediaGallery max 10 items")
    formatted = []
    for item in items:
      media = {"url": item.get("url")}
      desc = item.get("description")
      if desc:
        self._check_len(desc, 1024, "MediaGallery description")
        media["description"] = desc
      if "spoiler" in item:
        media["spoiler"] = item["spoiler"]
      formatted.append({"media": media})
    super().__init__(12, items=formatted)

class File(BaseComp):
  def __init__(self, filename, spoiler=None):
    super().__init__(13, file={"url": f"attachment://{filename}"}, spoiler=spoiler)

class FileUpload(BaseComp):
  def __init__(self, custom_id, min_values=None, max_values=None, required=None):
    super().__init__(19, custom_id=custom_id, min_values=min_values, max_values=max_values, required=required)
    self._check_len(custom_id, 100, "FileUpload custom_id")
    self._check_range(min_values, 0, 10, "FileUpload min_values")
    self._check_range(max_values, 1, 10, "FileUpload max_values")

class RadioGroup(BaseComp):
  def __init__(self, custom_id, options, required=None):
    super().__init__(21, custom_id=custom_id, options=options, required=required)
    self._check_len(custom_id, 100, "RadioGroup custom_id")
    if not (2 <= len(options) <= 10):
      raise ValueError("RadioGroup options 2-10")
    for opt in options:
      self._check_len(opt.get("label"), 100, "RadioOption label")
      self._check_len(opt.get("value"), 100, "RadioOption value")
      self._check_len(opt.get("description"), 100, "RadioOption description")

class CheckboxGroup(BaseComp):
  def __init__(self, custom_id, options, min_values=None, max_values=None, required=None):
    super().__init__(22, custom_id=custom_id, options=options, min_values=min_values, max_values=max_values, required=required)
    self._check_len(custom_id, 100, "CheckboxGroup custom_id")
    self._check_range(min_values, 0, 10, "CheckboxGroup min_values")
    self._check_range(max_values, 1, 10, "CheckboxGroup max_values")
    if not (1 <= len(options) <= 10):
      raise ValueError("CheckboxGroup options 1-10")
    for opt in options:
      self._check_len(opt.get("label"), 100, "CheckboxOption label")
      self._check_len(opt.get("value"), 100, "CheckboxOption value")
      self._check_len(opt.get("description"), 100, "CheckboxOption description")

class Checkbox(BaseComp):
  def __init__(self, custom_id, default=None):
    super().__init__(23, custom_id=custom_id, default=default)
    self._check_len(custom_id, 100, "Checkbox custom_id")

class V2Sender:
  def __init__(self, bot):
    self.bot = bot

  async def send_msg(self, interaction, root_components, ephemeral: bool = False):
    route = http.Route('POST', f'/interactions/{interaction.id}/{interaction.token}/callback')
    
    flags = 32768
    if ephemeral:
      flags |= 64
      
    await self.bot.http.request(route, json={
      "type": 4,
      "data": {
        "flags": flags,
        "components": [c.to_dict() for c in root_components]
      }
    })

  async def send_modal(self, interaction, custom_id, title, labels):
    route = http.Route('POST', f'/interactions/{interaction.id}/{interaction.token}/callback')
    await self.bot.http.request(route, json={
      "type": 9,
      "data": {
        "title": title,
        "custom_id": custom_id,
        "components": [l.to_dict() for l in labels]
      }
    })

  async def send_to_channel(self, channel, root_components):
    route = http.Route('POST', f'/channels/{channel.id}/messages')
    await self.bot.http.request(route, json={
      "flags": 32768,
      "components": [c.to_dict() for c in root_components]
    })