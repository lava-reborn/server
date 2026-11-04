"""Baked ReFlash states: native mesh/chrome and one olive-shadow caption.

The two 83 x 45 states contain the complete final picture, including text.
There are no text fields, font lookups, default labels or runtime filters.
PNG review files remain local; the client embeds these lossless SWF pixels.
"""
import base64
import struct

LINKAGE = '__rf_button_art'
OWNED = {LINKAGE, '__rf_caption_art', '__rf_up_bitmap', '__rf_down_bitmap',
         '__rf_up_shape', '__rf_down_shape'}

# DefineBitsLossless2 bodies without character IDs: format, size, zlib ARGB.
FRAMES = (
    (
        'BVMALQB42u1aZ4zl11WfmTe9z+z0nS2z09tO77332ek7vffee93Z4hKDIP4AKEWAQIIo8IFgI0ILRIqxE4IsRAiOSUhI+IQt'
        'IUyUtc3h9zv77uR5mV2v7ZB82Scd3Xbuvef87jnnlv+zs3v6e/p7+nv6e/r7efyqQgIubGWkXH+zv/vmO4uzMzI3NSnT42My'
        'OTqieUPWtneG+npldHBABnq6f70oL/fNmYlxWZiZlqW5WVldXHhnc3VFVhbm35mfntL6qbFRmRgZfhOk42+trcrh7o7cOjyQ'
        'g51t2V5fYz+db2SgXzge+Vi/t7UpOxvrsru5cZaS2MYy+1vrWqEHx/5FYFgfHXH5pcrSItnf3lKZTg72lUz59OhQbh8fqd6U'
        'm+UXnn1Gnr1zWz71zD35peeeVT0MLmy/d3pLnr93V/txjOP9PeV75vaptt85OdY2zsN+68tLsrGyLGtLi2drSFyJN3nu3jo5'
        'G9vIw5RtrOd87EM5gP/ftd9o3ggLCnTG7+eB4ZWQAL/fyUq7/v70+Ajk2YM8x5rubKwCxw1Nt9dXoOsW9FyUoz2u/ZrWs+5g'
        'Z1P5mLLd9NvbWte6k4Nd5V9fXtBx5qbGZX56ArY6q/Xk4zick/wzE6PAYUppeX5G+3DcrbVlzZu2pblpbWfK8RZmJnUOjk9d'
        'JkeHtA30rZKC3CxvL4//TxzrfD3d3mhtqpe+mx3y3N1T2Vxdgk3Mq26k4/0d1ZmyUWdiRP2N3syTj/XsS16DKzE1uBKH1cW5'
        's3XhWFwTjk+cDG7EwWDCerM27Mt2g53BkfMxZR+OQX7ysp3pUF+3rg3G/fHoyMBRdNQ1B/ufLYYcbyDA1+vdztZm6e/ulJbG'
        'OhkfHlAbun2yL/Mz41JfUy4NtRVSVV4k5SX5UlqUq2llWaGUFedJbVWp1FSWaD2JebY3N1Rrn4rSAqmrLlNeW2IbednfjEVe'
        '08Y+Zr7qimJNWc92Mz9lKy7I1rzhMWXmW5vrZHEOMWJiWHpvtkl/T4cszE/J+NjQZzIzUpx+Rng6ODjY1fv5eqst0j7oHzca'
        'amV2ckxtkvJS15amWtWBcrOusa5S9aGuxJhylxTmaDvbDHYGA4PdjcYaxY1jME8ejk/dyccy25myTD72M20Gd8rSVF91hp1Z'
        'S/Izz7GrKwqRZ78S5e9obZSj/S2ZnRqVm12tMglsp6fGfvVaxCUHO/tPbI8XXZwdv1tdVaF+NzLQK8P9PeqzvV3t0lhbpTKV'
        'FefI9cQo8fdxleyMJPH1cobumXIp7ILWX/B1k4LcNAkJ9NY06IKn8mWkxktu1nWtz8lMlqiIMEmMi5DLFwMkLztFvNwtkp4S'
        'hzXIUoqJDFe+AD93Lft5u+g44aH+Ok58zBXtFxrkIylJ0eLj6aRljpeZliCB/h5azzk4DuXiOClJkcCxXmUuLcqWof5OmZgY'
        'kM7OJhke6iWu7RfDgxzsHT42lo4WB7vfi4mOlPm5GcWwq+2G2mJTXbVUl5eoPcRFX1Z5qQ9lJ54tTdUSHOClFHE5WDrbGhQv'
        'Etvra0rFYmeneeJOHcOCfWGreXIlPFDL1JNl4ufp5qC4cbyk+GtqT+wXeTVUeYkH+xNjrhOJYzfWlWsdiX2JFeU047Pd38cZ'
        'clt03ZrqK1TW5oZK6e/vUDwrYK/jY4NvtLQ2RLu6WT6OfVrQ5UZwUIDiONDfK4yV3FOY0ibp56FBfmqTft5O8OMS4BaImNMP'
        'zDzlZkcD5PeQkcFOYGEno0NdkN9F04shPjLQ26rl4YEO5Rvsa4P9+MvEaI+OQ74AP1ft7+3hgDjWLB6udjI+0g0bi5OZyQHt'
        'Nzc9BOzctT00yAtY1Ok43Z2N2s7xmE6N92HdwxEbq8TVyQ621w5M3WCPtYpnbVUh8LSHXSRjrYuloaFCZmZG1Dbr68ult6/z'
        'N5KSYx0/IpYO9vb2XliBv87OysCajMjgQJ+MDfXruaGjpUmqyorlcliwxiKuN2UhfiuLE6r/pTA/xWlteUr1jL4WKlcvBcjW'
        '+pzWUwfa5fLCuPKSj/hdCb8g164EKR/LxJw4kI/rQb6i/DSt4zwHuyuKW0LsZZ2HeHEuw8/+JPJxfmLNMtebY5Aoz/zMsI7H'
        'taJs5SXZil9JSY4MD3crru0dze/CNmNgm5aPgKcjqMnXx+t+c1OD9HR3SWdHm+7btZVluoenX0+U5voa2KObjA33qB6Un3Ks'
        'Lk3q+u5uLarvEF/qtbO5oPZl2okX5d9cm4V/esvh3qriSj6Ox5Q4EQfivr0xL6nJUbKxOqP99raXtB/H8/VyVH72X5wb1XVd'
        'X5lGDAhWOcw8xJL9OT77U969nQXx93WUyfFu8fV2ULvlOK2tNdLSUq2YDg52SVt7g3TdvPHZqxEXXZ4QS0ZXN9Czly9dlO6b'
        'nUr9fTelp7NN2m80Sl3Vg33YxWKnWDL2UE/KSeyo19H+mq4xfZ/4HR+sizP43ZzttJ38jvZ22odE2akf9SUOrKP+xIc2T8y4'
        'P5BYNjiSj/wcnynbwkN91faIP/uzzLHJv7+zrPhRBq4vxyGOHsgH+DvL+uqkys1xaOvNzZWw0Vzp68M+21gpzTfqvpGVnRrm'
        'YLF7krjJOOkP+rfaStj1jWbdqydGBtWvefZqbawVbzeLLM5MSKCvO/b3WfGiXFh/V0c7nMcXNN3E+nu4/DTdh9yekPMA+njD'
        'Lll/ATIbu6GdEg/iSX2JN+vZTt2IA9eG9aad+HDeAPgp5QgDtkew7yC0swwH05TyMA3EeIewc87LfpR7a2NG7ZH2yZR8/pin'
        'q7UBMbdZOlsa9azVdqNeqipL36+prWh3c3dyfgIsXfC75Orscr+8uIjvD9Ld0ar7N89ePMOGBfqIn6ezyrm9tiA+sDti851/'
        '/ur/IeLF9vPaiOt59cTNpIxlxp8ZB+nvLBNT8mj8Bd8l2F4o1oE4PTwe15G4MR+C+OgHmzQ4si4owFWODlbEDXzennaqF+2B'
        '9lJXWSxDvV1SVpj7wB8barCvl+4FBl7wdHC0N378qJ8HOOJAP4mOuCoNNdVSU1Gq4wz0dqpdDvV2iCv8dX9rRXzcHdXejFzj'
        'YyUfINbRDs9rM+2Pqzd26A49iSNjAXFlO+Mr023g6e78QH/FF3b18Fj+VuxZZjtx38G4ps4d67q9OatYchyuz9Rov5TkZ8ro'
        'QI+UFuQoBuVlRdJQX/vFy5fDA6x2aXkMlj5gSSOW8dFRwLFczz68g3d3tuh9IDTAW1bmJ3X93OA7xn+MXJSDcl6w2pctNm44'
        'i9AfaRfGLllPW6MNMs4ylpl64sh61jHumvzD49463BBfxGpTZp5zUQ7O94H1QX/KzHZTx5hJHOnnbKefUc+R/i4Zxl5RUZwP'
        'u6qU4qI8qamu/HpsbHS4FcvHPSj5OzpYcl2cnO9XlBQDx3rFsaKkEOe8HuzZfTIx3Cterg5y79a++Ho4qV3Sj87zV8pl9HiY'
        '1nG+Oc+/6be2GJv4SXsklrtWf7XFh+u2gX2bcdKMZeIe8XxUDDpbY8h/crSm9sk4wbWgnvlZKTI22CtVpYW6X9Aui4sKvp2a'
        'ej3K6t1uj8EyAHDng+5XlZXiblOm50n6OX18cmxQrl0KliA/D/F0sZed9Qdxx8TE83zX6PGkPu5n44/mLMp9mvuxwZn7Mts3'
        'rf5Anw2+8GAfJJ6268f9Zt8aFx41P+0RT2zi52NRm+W6RF4OkbzM6/D1QakpLxa+1eKdQ240N/5jTExUotUuPZ8Ey4L8XMZZ'
        'KSvKl/LiArXLUdxNuV60x5P9Td3HKaetf9EOTPxkvW281H0b8YjtSzgHmnqepejPPHfu2ehNXM25lOdFnq0fZVscl3ZIeYgn'
        'y+fFS8ZXttviS7vc3Z5XX6e85F9bnIZv58rsxIiUw7d5Zy4tKRCcuf/Wx8cr1Yql9+OwhI/ng95NT0uR2poqPZsTS75H8V0q'
        'LvKSbK1iP0C84X5u/Ogs9qBsi5+tHsybdu4XZ/XA2N96PrK1S+LL+Ej79LLaN/nOsy8TnxlXOAfj+ZF1f7K1QbbRV2z9hRjS'
        'Jrn/ML6SaCfLcxN69stKTVKbWl6ak/i4mC/g7Szd4qRO7vNhWALyHyfExzLO6hjEk29qfKfk/sZ4ebiD87jzT+P7mb8AD+pl'
        'zidm/R8ms++yD8/V9F+e3w/OOdcov02chBqKs96HbOIr8Xu4H+WzxZLnNPqLideso3/vbM2pfRJ/xgXur0uzeGueHpeC7HQp'
        'ysuW7Kw0yc/L+bS9PfbnBzu4zxP4+Nf4rlFfVyOFuXjvKsjV98at9SWcEW6qPTJenh5uqx0Qy2BrDGOeMYfyLM+PaR3j2Xnx'
        'cgX3Tqbcv7nPMDbS34nrefzbVlzIx3O63nfg97Rx1nM+xo+H+xEfw0NZiCflY5xXfNenz+Il5Sf+xXkZsMkx6e1sRdxMVZtC'
        'vHwrNSV5DVgmW33c6zFYXgBLLuizeEzWvYdnAe5hxLKrvVn9u7QgS8/p9AOzzrQznnMY/yPwjsB1p9yM47RT2g/vJeSj/ifA'
        'IQbnb+4f9GGmvPvR/ng35D2H+w3jJbHjvZ7+z/cN+v0ScGM/xouLwJX6X8b5k/7AlLiaew7bycd5yReOecx96XB/We+Q9G9X'
        '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'
    ),
    (
        'BVMALQB42u1aV2ylx3W+vJeX5GUnl22rtnHZe6+Xvffee++dS3K53NU2FctBYj0kgQuSIAESw8lDHCmI05wYsCLZcSAEcRxZ'
        'sWPHzlMkIIhieCXl5PsO79DXa+5qJTn2y17gYP6ZOXNmzjenzD//tVie/J78nvye/J78fhG/yqiwkO2MlMQ3B3o631mam5b5'
        '6QmZmRiVqbFhfTbk6ntnuL9Hxob6ZbC36zeK8rLfnJ0ck8XZKVmen5G1pfl3ttaWZXVx7p2FmUltnx4fkcnRoTdBKn97fUWu'
        '727L09f3ZH9nS65urHKczjc62CeURz62721vyM7mmuxurR+VJPaxzvG7W5uk1qiwE5C99svAsC76wrmXKkqK5NrVTV3Tzf1d'
        'JVO/dXBNbt/YV725btZfePauPHvnafnEM3fkk8/dU70MLuy/d+uGPH/vto6jjBvXdpTvmds3tf/Ozevax3k4bmNlUTZXl2R9'
        'eeFoD4kr8SbP3acPjmSb9bBkH9s538zEuOK5NDf79+3NTZunIsK98PtFYPgU7PB3s9KS3+e6dT23sd6DXdnZWpVrOxtaXt2E'
        '7extyebaohxc25bd7TVtZ9v+7qbysWS/Gbd3dV3bbl7fUf6N1QWVMz8zLguzE7K6NKvt5KMczkn+2alRWZqfUlpZnNExlLu9'
        'sazPpm95YVr7WVLe4tykzuHuR/QN0DedBblZgQF+/5841gb7O95obayT/u4Oee7uLaE/rq/Mq26kG/tXVeeZyRHVmRhRf6M3'
        'n8nH9q31JeU1uBJTgytxWFueO9oXyuKeUD5xMrgRZ4MJ283ecCz7DXYGR87HkmMog/zkdcUXYfxhjAC+PxobHTyIvnzR6vHz'
        'xZDyBsNDAt/tbm9hnBPiOTEyqH5G/dZXZqWxrlzKnLlK1RVFUlvllLrqEqkqL5SSomypqSyWyrICLclTXpKnRF5SRWm+lBbn'
        'aEk+9nEcn0nkoazigkydi/2FeenaV19TqrzsZzvnIB/rhlh3FmYpX35OqrZxPo7vaG04stex4T4ZGeyRKdjD/NzUpzMzUuw/'
        'JzytVqtHXXBQgNoiYzl9oqmuWkvaZEtjla6T6yd+JIOL0YmYGiypf1N9hbaRDPbsI0YsKYNtlG3GES+2cazBkP2UkZuVrNhw'
        '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'
        'mOgzLiwfdaEU6mm15Xrbve6XO4txhqxTHHm3Nj7Sr3cWS7Pj4oP5yopwrvP2wLtQu/rO3NTg0brCcB7mvnNNps2UKwvjivv+'
        'zor6pmlfBT99l3Ew0GWvbN+7uqznFvo5fZ7x1Wax/IzcqxvzOq+pEyczD3F252Wd9unpJod5iXbJOEt9FmfGJD8rRcaH+qSy'
        'BO+lpcVql8VFBd9KTU2+7PJuxyOwDAPc+aD7laW4lygr1XsMYtnX3aZYno0KlWA/u4QFOaSvs1njPH3G2OWDxP03ejxIC8Dl'
        'OP8mbkZHxkvj58vYB75fBR2zR4x9zDNm/9RufQ5jN3HjOo9bgxnP/ENfpxziSbsszEmT6bEhqS4rVgxwzyHNTQ3/dOXK5QSX'
        'Xfo/DpYF+bmMs7ofPAfNTY9pzKRdch7GEvo47ZF+wfzt7q/uz8T6w/i4iZd8Zn5hnfmI8XLd5ZeMl8bOWV9EndgZe3ffP+4z'
        '7fZhMYjl/OygntnoZ9z/q+uL8O1cmZschQ/mKQYlzgLBmfvvgoICUl1YBj4KS/h4Pujd9LQUqamuVLssKy6Q4YFuvZe6dC4K'
        'Np+vtumNWMZzDeOl2XddI/bV2Cn9xdif4uSqc5x7jGX+pn+zdLjFNuZz2ib9nmWQm909aFuUR7nmnLAJ+zZ4cV53G34wLjGf'
        '89zL/aCc8GBfmZ0Ygu1MSlZqopQW5cvK8rzExV75vNVqSbfZ1cmDPghLQP6j+LgYxlndD+Ywnol4HzU50qd5h3YZ6LBp/uZ5'
        'bGai/2hd1IfnPPdYb56ncD5knXpS36M46sKR/mx3a2eeYd2cPzVueFuOtS/6hyk5P3Fxz3umDMV7IvO1u7/wXMQzPc9pkXif'
        '3NlY0pi5ODMhBdnpgm9Tkp2VJvl5OZ/y8EB+PszgQY/h41/lvUZdbbXkZqYplgW5GXovPTrQpTYZdSJAWhuqFBfGJPc8wpjF'
        'veU5jW3E+jhb2tlcOBrDfEKs6M/E9Tj+eTf7Ju7MV8SFurvb5oPjGC/dseR+mjWaNr4/eblsmnkrKzVe/byvsxXnllS1S8TL'
        't1JTktaBZZLLxwMegeUJsOSCPkN8mHt4FigpzMM9YJbm8r2tFSnKTde8w7hJ/2Y+7OtqVL8xWPJ9hzgvuuIa139cvCQ+Ji4y'
        'r5j3mm3Et+P4GTf1GedaYk9/4Lycj+08r9MeHxxn8raJM3oe9zi8PzB5nO+75IvCfRFxXF2Y0nM6KTM1Cfmj+J/Dw0J7gFOM'
        'K4/7PgLLEOCYYfOwbsNO/jMlIV7KnYU4Z5bgXq9c8aTtX9telfSkGI2X5r2N+0kboQ0yD3Hd7GMcNe8hfKZfM15SX55NmE8Y'
        'A+m308CFz2xjfRxxl3jRx3m+ZMykPTKfG74I3IEST85P36B/cy4+E1+W7ON5iThzXYyXXAvXwXMQz5bmnoXxqbm+TK7vrKuP'
        '0ybp4/RP5J7fAT6NwOm8yy69H4FlAF7aE+w2z0Fg+VehgQF6b1mQk4m75wTcladKY81P5om5eEbtkvtLu2PZ1lQpZ3HPwvMl'
        'dWI85frNezn1pi6M+7TfYeRN2iHtjOfIkcEOzTe0T+JIuyVuvbB7lsSb9suS/cYfDE7Mw9xTU9L+iCPjI/fRvI8zP2pcd91P'
        '8R4qKsIX31Y38d13S20yIzlWcUxPiqN//sepk+GbgNCJ3BPpwtLzEVj6wCYvIP80+HjabgHP/0qIuSwpCbG4w3fi/j5P3x27'
        '2xpk/+qaPHNrX/LxreAc7rXP4DsA8eT6qRNtjjibfH0S963GfoztjAI34jMFfWlvxJL33mPcH+vh3br6Meye94rkI468M+cd'
        '+RDsn7GSc3EfzXuA2S9j+9xH1um7xJHvvWynTRO/q1tzes/He7mDvTV9D22oLtUzUWZKgjjzs9/Hd+w/AnyT+l7ogfdDm+WD'
        '3sf5xh7O/IO1LYD9D3y9bO/FRV+EXoF6Xuf5ldTf1aKxk/vIvef5LS76jL5/R1+IUj8/j28Exi4GeppVT+pLvGmXrY0VihO/'
        'GfC8SIwGYT/8PkM/pn3OIa/WVRfjO/igYs17EOLd0VqjWFOOiTO0UdobMaJfEDviRj/nvhI/xu+Olmr8j2Fd17m3s6gYPntv'
        'T67tLmk+rMJdMG0yLfEKynicWbJe9/ex3wIuLaBLfN9xnYk+6HuZPygG1O5p86Btvn7mdKR+76GvZ6Yl4rtTtvp7S2MNzjAL'
        'cvvmrhzsbuA7+FVZmZ+E/iMyMz4IPxyUhelR4DWkZ/zlBfRNDms/70jmZ0aVZ2l+QnlI7GP71PjAUf/C7Jg+szREWYtz48q/'
        'ujSt82yszsn81IjKmRju1TGcjyVjEnl5ZiQ/z3acl/L399dVj5XFKegXj+8WCRrTkuKjBf87ePtMVPjngMMiMMmz2TzCgJP9'
        'Me+Dcd1kiQDlgeYw5EWM/25UZDjOBLDJgjzhOT4lOVFyc7L0vaodd5orC7Ny985N/Q/CzRuu/6vcOjj8/8nT1/X/KGznfz2e'
        'vrl/+F8W1K/v78jB9V19Jh+J/azfONg7qrsT+wyRhyXl37l9Q+VSnv73BWP5Pxfl3T+cw8zLdVEW5x/G+aS2pkr4TQZncRkd'
        'GZLBgT68fzv/G3n7j73sttvAoRV4RLtyN751Wx/3bp38F/i/IYzZQflZT0/Pb4eFhUlCQoLk5+dLXl6epKWlSUZ6qq6BJbEl'
        '1iXOosP3zwreUzm15LmfZUV56RGZPtPOMQ8j93FmDInvZvzmTJ7SkmJxFhfq/OzD/RjuHGt1biPDjOMYjq2oqJDExERJT0+X'
        'goICSUlJkdLSUiksLHw7ODj4z/z8/F7E968pYJCNkjZmR/mhvueCgkFJGNdjs9lu4/m3QV+D7P+5dOmSZGRkSHZ29pGNJibE'
        'Cc6xkpWZzncDbWedlJaarMRn8pJMH23d8CYnwa8S45X47M53HBlZJMp3l8M21s28LLnfZj72k+/y5cuqC+0iNRX9mfjuGRz8'
        'r/h/1p/Cfj4L/TehdzXPQcDBD7Zl+5BYWl13c9yHLIwfhty7Ljy/BJnfjYyMfD8uLk6KCmGjudlqmwZTlnwHNVhRB+pisDJ6'
        'mj53nQ1+Bn/yuPMZHsoimfnYn5Odqeswc5l+M6eRadbJNebm5ip+xDE2NvbtiIiIf4COL1NX6HyAsh2UQNuC3h/WJn/qOxpw'
        'PIkyBzSIvboJ+jSe/xD01/ie8X0kq7dCggN1XcSU2OKOT/U2dmCwcMfNYGmwM3XaNenBcQ8j8rrJ/V8XvY+294Dru+i/z2fM'
        'cx/4vZcQH3sfGL8Lnh9D/v34+Pi3Tp48+b3AwMBXAgICXrbb7Z8HXr8OvXehYxcoDRTpuqu0fbz/E1kdLlk4V3m0YW/4h88X'
        'QL9FTJHrX8K39FexW98AfYff3VB/hXX0vQH6AWL3D/Ffmh/4+zne9PP1ed3by/M1tP8F+L4Kvq+j/BZ4/s3h4/VD9H8P9Cb4'
        'v4E65XwJ+/W34H8VPP/o422njO9TVoC/7zdBr4Lvy+j/IvheBv05nr+CttfQ9xp4XwF9GeNesntav4i+34Ocv0T/n6D9C9Dv'
        'c8DvRejyPOgmdFx2OBwDeK7AcxJtCeSPZ88POE8+Lp4+oFBXHisAdaA+Bx/Yg653QS+AfhWYvIj1fgrrfRb159kG+gToV0DP'
        'of856HrPNeYAtA+646JnXO33wHPLRTdQ33Gj6xyD9n3McQ3E8dugFdACaAo07qJR0AhoCPP2YV294O/B2DZQB/Oy632wBlQK'
        'ffLgZ7TBWOZd6BYF/IJBviC7C0frR/TxB/FkrPADhcE2z6GMQ3smz/XYZyfKElAp37E8mPNwpsKa2ZcHXfJQz+G7votSQAno'
        'S4B+SehPc31nYl8qxqWhLRF98SijQVdAMWjnd704N7rCszPoAugMeE5hzCnwnUI90kXhaI9AO+9teN8Q7FbyLtcfuNH3fPh+'
        'DRv1gq7MFXb+XHn449rjw2KozXUG5Xu9A+vxfYDY5uc68/u5yLT7gLxBXi6yu8jrIaXnY5DNRdbHpCe/J78nvye/J79f7u//'
        'AFEL+Bw='
    ),
)


def without_artwork(tags):
    """Remove our previous states before allocating any other injected art."""

    def exports(payload):
        at = 2
        for _ in range(struct.unpack_from('<H', payload)[0]):
            cid = struct.unpack_from('<H', payload, at)[0]
            end = payload.index(b'\0', at + 2)
            yield payload[at + 2:end].decode(), cid
            at = end + 1

    old = {cid for code, p, _ in tags if code == 56
           for name, cid in exports(p) if name in OWNED}
    clean = []
    for code, p, long in tags:
        if code in (2, 36, 37, 39) and int.from_bytes(p[:2], 'little') in old:
            continue
        if code == 56:
            rows = [(n, i) for n, i in exports(p) if n not in OWNED]
            if not rows:
                continue
            p = struct.pack('<H', len(rows)) + b''.join(
                struct.pack('<H', i) + n.encode() + b'\0' for n, i in rows)
        clean.append((code, p, long))
    return clean


def artwork(tags):
    import widescreen as w
    from swfgen import shape, place2
    clean = without_artwork(tags)
    definitions = {2,6,7,10,11,14,20,21,22,32,33,34,35,36,37,39,46,48,60,75,83,84,87,90,91}
    used = set()
    def collect(items):
        for code, payload, _ in items:
            if code in definitions:
                used.add(int.from_bytes(payload[:2], 'little'))
            if code == 39:
                collect(w.split_tags(b'\x08\0\0\0\0\0' + payload[4:]))
    collect(clean)
    symbol, up_bitmap, down_bitmap, up_shape, down_shape = sorted(set(range(1,65536))-used)[:5]
    added = []
    for bitmap_id, shape_id, encoded in zip((up_bitmap, down_bitmap), (up_shape, down_shape), FRAMES):
        pixels = base64.b64decode(encoded)
        fmt, width, height = struct.unpack_from('<BHH', pixels)
        assert (fmt, width, height) == (5,83,45)
        added.append((36,struct.pack('<H',bitmap_id)+pixels,True))
        added.extend(w.split_tags(b'\x08\0\0\0\0\0'+shape(shape_id,bitmap_id,width,height)))
    children = [(12,b'\x07\x00',False)]
    children += w.split_tags(b'\x08\0\0\0\0\0'+place2(1,up_shape))
    children += [(1,b'',False)]
    children += w.split_tags(b'\x08\0\0\0\0\0'+place2(1,down_shape,move=True))
    children += [(1,b'',False),(0,b'',False)]
    added.append((39,struct.pack('<HH',symbol,2)+w.join_tags(b'',children),True))
    names = ((LINKAGE,symbol),('__rf_up_bitmap',up_bitmap),('__rf_down_bitmap',down_bitmap),
             ('__rf_up_shape',up_shape),('__rf_down_shape',down_shape))
    exported = struct.pack('<H',len(names))+b''.join(
        struct.pack('<H',cid)+name.encode()+b'\0' for name,cid in names)
    added.append((56,exported,True))
    at = next(i for i,t in enumerate(clean) if t[0]==1)
    clean[at:at] = added
    return clean
