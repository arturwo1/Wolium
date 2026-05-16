from nextcord import http
from typing import Optional, List, Dict, Any
from enum import IntEnum


class ComponentType(IntEnum):
  """Типы компонентов Discord V2"""
  ACTION_ROW = 1
  BUTTON = 2
  SELECT = 3
  TEXT_INPUT = 4
  TEXT_DISPLAY = 10
  THUMBNAIL = 11
  MEDIA_GALLERY = 12
  FILE = 13
  SEPARATOR = 14
  CONTAINER = 17
  LABEL = 18
  SECTION = 9
  FILE_UPLOAD = 19
  RADIO_GROUP = 21
  CHECKBOX_GROUP = 22
  CHECKBOX = 23


class ValidationError(ValueError):
  """Кастомное исключение для ошибок валидации"""
  pass


class BaseComp:
  """Базовый класс для всех компонентов"""

  def __init__(self, c_type: ComponentType, **kwargs):
    self.payload = {"type": int(c_type)}
    for k, v in kwargs.items():
      if v is not None:
        self.payload[k] = v

  def to_dict(self) -> Dict[str, Any]:
    return self.payload

  def _check_len(self, val: Optional[str], max_l: int, field: str) -> None:
    """Проверка максимальной длины"""
    if val is not None and len(str(val)) > max_l:
      raise ValidationError(f"{field}: {len(str(val))} > {max_l} символов")

  def _check_range(self, val: Optional[int], min_v: int, max_v: int, field: str) -> None:
    """Проверка диапазона значения"""
    if val is not None and not (min_v <= val <= max_v):
      raise ValidationError(f"{field}: {val} не в диапазоне {min_v}-{max_v}")

  def _check_option_list(self, options: List[Dict[str, Any]], max_count: int, field: str) -> None:
    """Проверка списка опций"""
    if len(options) > max_count:
      raise ValidationError(f"{field}: {len(options)} > {max_count} опций")


class Container(BaseComp):
  """Контейнер для компонентов V2"""

  def __init__(self, accent_color: Optional[int] = None, spoiler: Optional[bool] = None):
    super().__init__(ComponentType.CONTAINER, accent_color=accent_color, spoiler=spoiler)
    self.payload["components"] = []

  def add(self, *components: BaseComp) -> "Container":
    """Добавить компоненты в контейнер"""
    for c in components:
      self.payload["components"].append(c.to_dict())
    return self


class ActionRow(BaseComp):
  """ActionRow для традиционных компонентов"""

  def __init__(self):
    super().__init__(ComponentType.ACTION_ROW)
    self.payload["components"] = []

  def add(self, *components: BaseComp) -> "ActionRow":
    """Добавить до 5 компонентов"""
    if len(self.payload["components"]) + len(components) > 5:
      raise ValidationError("ActionRow: максимум 5 компонентов")
    for c in components:
      self.payload["components"].append(c.to_dict())
    return self


class Section(BaseComp):
  """Секция V2 с максимум 3 компонентами"""

  def __init__(self, accessory: Optional[BaseComp] = None):
    super().__init__(ComponentType.SECTION)
    self.payload["components"] = []
    if accessory:
      self.payload["accessory"] = accessory.to_dict()

  def add(self, *components: BaseComp) -> "Section":
    """Добавить до 3 компонентов"""
    if len(self.payload["components"]) + len(components) > 3:
      raise ValidationError("Section: максимум 3 компонента")
    for c in components:
      self.payload["components"].append(c.to_dict())
    return self


class Label(BaseComp):
  """Метка с описанием и опциональным компонентом"""

  def __init__(
    self,
    label: str,
    description: Optional[str] = None,
    component: Optional[BaseComp] = None
  ):
    self._check_len(label, 45, "Label label")
    self._check_len(description, 100, "Label description")
    
    super().__init__(ComponentType.LABEL, label=label, description=description)
    if component:
      self.payload["component"] = component.to_dict()


class TextDisplay(BaseComp):
  """Компонент для отображения текста"""

  def __init__(self, content: str):
    super().__init__(ComponentType.TEXT_DISPLAY, content=content)


class Separator(BaseComp):
  """Разделитель"""

  def __init__(self, spacing: int = 1, divider: bool = True):
    super().__init__(ComponentType.SEPARATOR, spacing=spacing, divider=divider)


class Button(BaseComp):
  """Кнопка V2"""

  def __init__(
    self,
    style: int,
    custom_id: Optional[str] = None,
    label: Optional[str] = None,
    emoji: Optional[Dict[str, Any]] = None,
    url: Optional[str] = None,
    sku_id: Optional[str] = None,
    disabled: Optional[bool] = None
  ):
    self._check_len(label, 80, "Button label")
    self._check_len(custom_id, 100, "Button custom_id")
    self._check_len(url, 512, "Button url")
    
    super().__init__(
      ComponentType.BUTTON,
      style=style,
      custom_id=custom_id,
      label=label,
      url=url,
      sku_id=sku_id,
      disabled=disabled
    )
    if emoji:
      self.payload["emoji"] = emoji


class Select(BaseComp):
  """Базовый класс для всех типов Select"""

  def __init__(
    self,
    c_type: ComponentType,
    custom_id: str,
    placeholder: Optional[str] = None,
    min_values: Optional[int] = None,
    max_values: Optional[int] = None,
    disabled: Optional[bool] = None,
    options: Optional[List[Dict[str, Any]]] = None,
    channel_types: Optional[List[int]] = None,
    default_values: Optional[List[Dict[str, Any]]] = None
  ):
    self._check_len(custom_id, 100, "Select custom_id")
    self._check_len(placeholder, 150, "Select placeholder")
    self._check_range(min_values, 0, 25, "Select min_values")
    self._check_range(max_values, 1, 25, "Select max_values")
    
    if options:
      self._validate_options(options, 25, "Select")
    
    super().__init__(
      c_type,
      custom_id=custom_id,
      placeholder=placeholder,
      min_values=min_values,
      max_values=max_values,
      disabled=disabled,
      channel_types=channel_types
    )
    
    if options:
      self.payload["options"] = options
    if default_values:
      self.payload["default_values"] = default_values

  @staticmethod
  def _validate_options(options: List[Dict[str, Any]], max_count: int, field: str) -> None:
    """Валидация опций"""
    if len(options) > max_count:
      raise ValidationError(f"{field} options: {len(options)} > {max_count}")
    for opt in options:
      instance = Select(ComponentType.SELECT, "dummy")  # для проверки методов
      instance._check_len(opt.get("label"), 100, "Option label")
      instance._check_len(opt.get("value"), 100, "Option value")
      instance._check_len(opt.get("description"), 100, "Option description")


class TextInput(BaseComp):
  """Текстовое поле ввода"""

  def __init__(
    self,
    custom_id: str,
    style: int,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    required: Optional[bool] = None,
    value: Optional[str] = None,
    placeholder: Optional[str] = None
  ):
    self._check_len(custom_id, 100, "TextInput custom_id")
    self._check_len(value, 4000, "TextInput value")
    self._check_len(placeholder, 100, "TextInput placeholder")
    self._check_range(min_length, 0, 4000, "TextInput min_length")
    self._check_range(max_length, 1, 4000, "TextInput max_length")
    
    super().__init__(
      ComponentType.TEXT_INPUT,
      custom_id=custom_id,
      style=style,
      min_length=min_length,
      max_length=max_length,
      required=required,
      value=value,
      placeholder=placeholder
    )


class Thumbnail(BaseComp):
  """Миниатюра изображения"""

  def __init__(
    self,
    url: str,
    description: Optional[str] = None,
    spoiler: Optional[bool] = None
  ):
    if description:
      self._check_len(description, 1024, "Thumbnail description")
    
    media = {"url": url}
    if description:
      media["description"] = description
    if spoiler:
      media["spoiler"] = spoiler
    
    super().__init__(ComponentType.THUMBNAIL, media=media)


class MediaGallery(BaseComp):
  """Галерея медиа (макс 10 элементов)"""

  def __init__(self, items: List[Dict[str, Any]]):
    if len(items) > 10:
      raise ValidationError(f"MediaGallery: {len(items)} > 10 элементов")
    
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
    
    super().__init__(ComponentType.MEDIA_GALLERY, items=formatted)


class File(BaseComp):
  """Файл в сообщении"""

  def __init__(self, filename: str, spoiler: Optional[bool] = None):
    super().__init__(
      ComponentType.FILE,
      file={"url": f"attachment://{filename}"},
      spoiler=spoiler
    )


class FileUpload(BaseComp):
  """Компонент загрузки файла"""

  def __init__(
    self,
    custom_id: str,
    min_values: Optional[int] = None,
    max_values: Optional[int] = None,
    required: Optional[bool] = None
  ):
    self._check_len(custom_id, 100, "FileUpload custom_id")
    self._check_range(min_values, 0, 10, "FileUpload min_values")
    self._check_range(max_values, 1, 10, "FileUpload max_values")
    
    super().__init__(
      ComponentType.FILE_UPLOAD,
      custom_id=custom_id,
      min_values=min_values,
      max_values=max_values,
      required=required
    )


class RadioGroup(BaseComp):
  """Группа радиокнопок (2-10 опций)"""

  def __init__(
    self,
    custom_id: str,
    options: List[Dict[str, Any]],
    required: Optional[bool] = None
  ):
    self._check_len(custom_id, 100, "RadioGroup custom_id")
    
    if not (2 <= len(options) <= 10):
      raise ValidationError(f"RadioGroup: {len(options)} опций, нужно 2-10")
    
    self._validate_radio_options(options)
    
    super().__init__(
      ComponentType.RADIO_GROUP,
      custom_id=custom_id,
      options=options,
      required=required
    )

  @staticmethod
  def _validate_radio_options(options: List[Dict[str, Any]]) -> None:
    """Валидация опций радиогруппы"""
    instance = RadioGroup("dummy", [{"label": "x", "value": "x"}])
    for opt in options:
      instance._check_len(opt.get("label"), 100, "RadioOption label")
      instance._check_len(opt.get("value"), 100, "RadioOption value")
      instance._check_len(opt.get("description"), 100, "RadioOption description")


class CheckboxGroup(BaseComp):
  """Группа чекбоксов (1-10 опций)"""

  def __init__(
    self,
    custom_id: str,
    options: List[Dict[str, Any]],
    min_values: Optional[int] = None,
    max_values: Optional[int] = None,
    required: Optional[bool] = None
  ):
    self._check_len(custom_id, 100, "CheckboxGroup custom_id")
    self._check_range(min_values, 0, 10, "CheckboxGroup min_values")
    self._check_range(max_values, 1, 10, "CheckboxGroup max_values")
    
    if not (1 <= len(options) <= 10):
      raise ValidationError(f"CheckboxGroup: {len(options)} опций, нужно 1-10")
    
    self._validate_checkbox_options(options)
    
    super().__init__(
      ComponentType.CHECKBOX_GROUP,
      custom_id=custom_id,
      options=options,
      min_values=min_values,
      max_values=max_values,
      required=required
    )

  @staticmethod
  def _validate_checkbox_options(options: List[Dict[str, Any]]) -> None:
    """Валидация опций чекбоксов"""
    instance = CheckboxGroup("dummy", [{"label": "x", "value": "x"}])
    for opt in options:
      instance._check_len(opt.get("label"), 100, "CheckboxOption label")
      instance._check_len(opt.get("value"), 100, "CheckboxOption value")
      instance._check_len(opt.get("description"), 100, "CheckboxOption description")


class Checkbox(BaseComp):
  """Одиночный чекбокс"""

  def __init__(self, custom_id: str, default: Optional[bool] = None):
    self._check_len(custom_id, 100, "Checkbox custom_id")
    super().__init__(ComponentType.CHECKBOX, custom_id=custom_id, default=default)


class V2Sender:
  """Отправитель V2 компонентов через Discord API"""

  def __init__(self, bot):
    self.bot = bot

  async def send_msg(
    self,
    interaction,
    root_components: List[BaseComp],
    ephemeral: bool = False
  ) -> None:
    """Отправить сообщение с компонентами на взаимодействие"""
    route = http.Route(
      'POST',
      f'/interactions/{interaction.id}/{interaction.token}/callback'
    )

    flags = 32768  # v2 flag
    if ephemeral:
      flags |= 64  # ephemeral flag

    await self.bot.http.request(route, json={
      "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
      "data": {
        "flags": flags,
        "components": [c.to_dict() for c in root_components]
      }
    })

  async def send_modal(
    self,
    interaction,
    custom_id: str,
    title: str,
    labels: List[Label]
  ) -> None:
    """Отправить модаль"""
    route = http.Route(
      'POST',
      f'/interactions/{interaction.id}/{interaction.token}/callback'
    )
    await self.bot.http.request(route, json={
      "type": 9,  # MODAL
      "data": {
        "title": title,
        "custom_id": custom_id,
        "components": [l.to_dict() for l in labels]
      }
    })

  async def send_to_channel(
    self,
    channel,
    root_components: List[BaseComp]
  ) -> None:
    """Отправить сообщение в канал"""
    route = http.Route('POST', f'/channels/{channel.id}/messages')
    await self.bot.http.request(route, json={
      "flags": 32768,  # v2 flag
      "components": [c.to_dict() for c in root_components]
    })