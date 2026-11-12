from publicsuffixlist import PublicSuffixList


def test_public_suffix_list_works_offline():
    # The autouse no_network fixture makes any download attempt fail this test.
    psl = PublicSuffixList()
    assert psl.privatesuffix("paypal.com.evil.co.uk") == "evil.co.uk"
    assert psl.privatesuffix("shop.example.com.cn") == "example.com.cn"
