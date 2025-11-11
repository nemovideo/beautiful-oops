import pytest
from beautiful_oops import Adventure, StorybookPlugin, StoryBook, oops_moment


def test_storybook_records_attempts_and_moments():
    sb = StoryBook("testbook")
    adv = Adventure(name="adv", plugins=[StorybookPlugin(sb)], debug=True)


    @oops_moment(chapter="Ch", stage="S1")
    def s1():
        return "A"

    @oops_moment(chapter="Ch", stage="S2")
    def s2():
        raise ValueError("x")

    with Adventure.auto(adv):
        assert s1() == "A"
        with pytest.raises(Exception):
            s2()

            cats = [fp.category for fp in sb.footprints]
            assert "moment" in cats and "attempt" in cats
            assert len(sb.treasures) >= 1
            assert len(sb.tears) >= 1
