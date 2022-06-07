from typing import Optional
from httpx import AsyncClient
from lxml import html

try:
    from helper.actress import actress_search
except ImportError:
    from .helper.actress import actress_search


async def get_page_content(client: AsyncClient,
                           url: Optional[str] = 'vl_searchbyid.php',
                           **kwargs) -> bytes:
    """Get the page content as bytes, takes url as optional argument."""
    return html.fromstring((await client.get(url, **kwargs)).content)


async def filter_results(tree: html.HtmlElement, name: str):
    """Filter the results from the page, if duplicate or more than one result found iterate over the results."""
    try:
        if name == (tree.xpath('//h3[@class="post-title text"]/a/text()')[0].strip()).split(' ')[0]:
            return tree

    except IndexError:
        # Probably Duplicate results or no result found
        for result in tree.xpath('//div[@class="videos"]/div/a'):
            if name == result.get('title').split(' ')[0]:
                return str(result.get('href'))


async def additional_details(tree: html.HtmlElement) -> dict[str, str | None]:
    """get movie director, release date, runtime, studio."""
    details, sorted_details = {}, {}
    for data in tree.xpath('//div[@class="item"]/table/tr'):
        key = str(data.xpath('td[@class="header"]/text()')
                  [0].split(':')[0].strip())
        if key == 'Director':
            try:
                details['director'] = data.xpath(
                    'td/span[@class="director"]/a/text()')[0].strip()
            except IndexError:
                details['director'] = None
        elif key == 'Release Date':
            try:
                details['release_date'] = data.xpath(
                    'td[@class="text"]/text()')[0].strip()
            except IndexError:
                details['release_date'] = None
        elif key == 'Length':
            try:
                details['runtime'] = data.xpath(
                    'td/span[@class="text"]/text()')[0].strip()
            except IndexError:
                details['runtime'] = None
        elif key == 'Maker':
            try:
                details['studio'] = data.xpath(
                    'td/span[@class="maker"]/a/text()')[0].strip()
            except IndexError:
                details['studio'] = None
        elif key == 'User Rating':
            try:
                value = str(data.xpath(
                    'td/span[@class="score"]/text()')[0].strip())
                for char in ['(', ')']:
                    value = value.replace(char, '')
                details['user_rating'] = value.strip()
            except IndexError:
                details['user_rating'] = None
    for key, value in sorted(details.items()):
        sorted_details[key] = value

    return sorted_details


async def parse_details(tree: html.HtmlElement, only_r18: bool) -> dict[str] | None:
    """Parse in details from the page."""
    # get movie code, title and poster
    movie_dictionary = {}
    movie_dictionary['id'] = str(tree.xpath(
        '//h3[@class="post-title text"]/a/text()')[0].strip()).split(' ', maxsplit=1)[0]
    movie_dictionary['title'] = str(tree.xpath(
        '//h3[@class="post-title text"]/a/text()')[0].strip()).split(movie_dictionary['id'])[1].strip()
    movie_dictionary['poster'] = 'https:' + \
        str(tree.xpath('//div[@id="video_jacket"]/img')[0].get('src'))
    movie_dictionary['page'] = 'https:' + \
        str(tree.find('head/link[@rel="canonical"]').get('href'))
    # get movie details
    movie_dictionary['details'] = await additional_details(tree)

    # print actress details
    movie_dictionary['actress'] = await parse_actress_details(tree, only_r18)

    # get movie genres / tags
    for data in tree.xpath('//div[@id="video_genres"]/table/tr'):
        movie_dictionary['tags'] = data.xpath(
            'td[@class="text"]/span/a/text()')

    # return movie_dictionary
    return movie_dictionary


async def parse_actress_details(tree: html.HtmlElement, only_r18: bool) -> dict[str]:
    """Parse actress details from actress module."""
    actress_list = [name.strip()
                    for name in tree.xpath('//span[@class="star"]/a/text()')]
    actress_list.extend([name.strip()
                        for name in tree.xpath('//span[@class="alias"]/text()')])
    return await actress_search(actress_list, only_r18)


async def main(name: str, only_r18: bool = False):
    """Main function to handle api call."""

    header = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.101 Safari/537.36",
        "Accept": "*/*"
    }
    async with AsyncClient(base_url='https://www.javlibrary.com/en',
                           headers=header,
                           cookies={'over18': '18'},
                           http2=True,
                           follow_redirects=True,
                           timeout=20) as client:
        # Fetch html tree, by query and filter the results
        result = await filter_results((await get_page_content(client,
                                                              params={'keyword': name})), name)
        if result is not None and not isinstance(result, str):
            return await parse_details(result, only_r18)
        if result is not None and isinstance(result, str):
            result = await filter_results(await get_page_content(client,
                                                                 url=result.replace('.', '')), name)
            return await parse_details(result, only_r18)

if __name__ == '__main__':
    import asyncio
    import json

    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    # Duplicate test
    # print(json.dumps(asyncio.run(main('SSIS-304')), indent=4, ensure_ascii=False))
    # Actressc count > 1
    # print(json.dumps(asyncio.run(main('STSK-032')), indent=4, ensure_ascii=False))
    # Single Test
    print(json.dumps(asyncio.run(main('EBOD-391', True)), indent=4, ensure_ascii=False))
    # No result
    # print(json.dumps(asyncio.run(main('TEST-123')), indent=4, ensure_ascii=False))