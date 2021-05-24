from inatcog.embeds import embeds
import unittest


class TestEmbeds(unittest.TestCase):
    def test_make_embed(self):
        """Test make_embed."""
        test_embed = embeds.make_embed(
            title="a", url="b", description="c", other="blank"
        )
        self.assertEqual("a", test_embed.title)
        self.assertEqual("b", test_embed.url)
        self.assertEqual("c", test_embed.description)
        self.assertIsNotNone(test_embed.color)

    def test_sorry(self):
        """Test sorry."""
        test_sorry_1 = embeds.sorry()
        test_sorry_2 = embeds.sorry("x")

        self.assertEqual("Sorry", test_sorry_1.title)
        self.assertEqual("I don't understand", test_sorry_1.description)

        self.assertEqual("Sorry", test_sorry_2.title)
        self.assertEqual("x", test_sorry_2.description)
