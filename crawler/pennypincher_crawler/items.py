import scrapy


class PageScreenshotItem(scrapy.Item):
    url = scrapy.Field()
    screenshot_file = scrapy.Field()
    title = scrapy.Field()
