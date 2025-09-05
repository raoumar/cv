"""
This script generates a word cloud from a given text, where different groups of
words can be colored with different color schemes. This is useful for research
purposes where you want to visually distinguish different categories of words.

To use this script:
1.  Install the necessary libraries:
    pip install wordcloud matplotlib numpy

2.  Modify the `text` variable to contain your own text.

3.  Modify the `color_to_words` dictionary to define your own color groups.
    The keys of the dictionary are colors (e.g., '#00ff00', 'red'), and the
    values are lists of words that should be colored with that color.

4.  Run the script:
    python word_map.py
"""

import matplotlib.pyplot as plt
from wordcloud import WordCloud, get_single_color_func

class GroupedColorFunc(object):
    """
    Create a color function object which assigns DIFFERENT SHADES of
    specified colors to certain words based on the color to words mapping.

    Uses wordcloud.get_single_color_func

    Parameters
    ----------
    color_to_words : dict(str -> list(str))
      A dictionary that maps a color to the list of words.

    default_color : str
      Color that will be assigned to a word that's not a member
      of any value from color_to_words.
    """

    def __init__(self, color_to_words, default_color):
        self.color_func_to_words = [
            (get_single_color_func(color), set(words))
            for (color, words) in color_to_words.items()
        ]
        self.default_color_func = get_single_color_func(default_color)

    def get_color_func(self, word):
        """Returns a single_color_func associated with the word"""
        try:
            color_func = next(
                color_func for (color_func, words) in self.color_func_to_words
                if word in words
            )
        except StopIteration:
            color_func = self.default_color_func
        return color_func

    def __call__(self, word, **kwargs):
        return self.get_color_func(word)(word, **kwargs)

if __name__ == "__main__":
    # 1. Provide the text for the word cloud
    text = """
    The Zen of Python, by Tim Peters
    Beautiful is better than ugly.
    Explicit is better than implicit.
    Simple is better than complex.
    Complex is better than complicated.
    Flat is better than nested.
    Sparse is better than dense.
    Readability counts.
    Special cases aren't special enough to break the rules.
    Although practicality beats purity.
    Errors should never pass silently.
    Unless explicitly silenced.
    In the face of ambiguity, refuse the temptation to guess.
    There should be one-- and preferably only one --obvious way to do it.
    Although that way may not be obvious at first unless you're Dutch.
    Now is better than never.
    Although never is often better than *right* now.
    If the implementation is hard to explain, it's a bad idea.
    If the implementation is easy to explain, it may be a good idea.
    Namespaces are one honking great idea -- let's do more of those!
    """

    # 2. Define the color groups
    #    You can use color names or hex codes
    color_to_words = {
        # Words in this group will be colored with shades of green
        '#00ff00': ['beautiful', 'explicit', 'simple', 'sparse', 'readability',
                    'rules', 'practicality', 'explicitly', 'one', 'now',
                    'easy', 'obvious', 'better'],
        # Words in this group will be colored with shades of red
        'red': ['ugly', 'implicit', 'complex', 'complicated', 'nested',
                'dense', 'special', 'errors', 'silently', 'ambiguity',
                'guess', 'hard']
    }

    # Words that are not in any of the color_to_words values
    # will be colored with shades of grey
    default_color = 'grey'

    # Create the word cloud object.
    # We are turning off collocations to ensure that phrases are not treated as
    # single words.
    wc = WordCloud(collocations=False, background_color="white").generate(text.lower())

    # Create the color function
    grouped_color_func = GroupedColorFunc(color_to_words, default_color)

    # Apply the color function to the word cloud
    wc.recolor(color_func=grouped_color_func)

    # 3. Display the word cloud
    plt.figure(figsize=(12, 8))
    plt.imshow(wc, interpolation="bilinear")
    plt.axis("off")
    plt.show()

    # 4. (Optional) Save the word cloud to a file
    # wc.to_file("word_map.png")
    # print("Word map saved to word_map.png")
