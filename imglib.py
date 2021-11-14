from base64 import b64decode
from io import BytesIO

_warning_sign_b64 = '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'

_refresh_sign_b64 = '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'

_help_sign_b64 = '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'

_info_sign_b64 = 'iVBORw0KGgoAAAANSUhEUgAAABkAAAAZCAYAAADE6YVjAAAACXBIWXMAAAsTAAALEwEAmpwYAAAAIGNIUk0AAHolAACAgwAA+f8AAIDpAAB1MAAA6mAAADqYAAAXb5JfxUYAAATgSURBVHja3JZriJRVHMZ/55z3Mvfd\
mZ3dddZ1d3V1bW11UfOeeSMhhMoUxAqMQg1DScySwqDQTEPRtIgKoqIvgYlgEZZR9KEbEbjlVrJK5V1Wd2cv48y87zl9mNlhbbQ+1YfOl/fwvofnOc//fZ7zP8IYw789JP/BsIYm+wEbMMDW8bfQ/esvqEAl0lV4fb0t0g0u9DP9E8BEpbIHVD\
DSmc+kP7Osqk4hBL7Xjeu6ZAYGAAGAMfp6khuJNF620UduNtpb62f6Smu1n0f3Xy0AiczrRohdQqiuf1QSKCoBkJYFiHXay7yCB8qykJZ1NJ/3j6tA8qrOXqmQgola+3f5Xt8aYI3lBDYhxJ4bshhjMMaw1xheNYZ9nqGyvn5noXLCgNxT01CX\
GnnrDJzYOFQoBTJCRWM74REjq0HsKKzDCCEO3Ai7NGma8gjj562levyS1YBBSqNiyfm4MRxH4UZGYzmj5gIfQGCZG23BCtiAC3ZyNpArbExtFMSBaDmJSjRAMF4LGCvgmvYHVs6asHIVTiKOG4JAEKSio+gNb3jFa1tup665rd1yXAPSxJvvGZ\
Wa9mg5SdXkRbg1Y94ADCp0INW2gJr2hdgVDcRHzybRNBs7XH0b8G5q1cMPzjjyCdM//JTEnXdTlWog1TgOy3FfAIwKBN934nUlbDEURjscbvQGB08DIpKoD1/r6R0U+FS0Pk20eQVSwfmvnogOXjgcTSxefK569kwMcPbgIQY6OobnLgcooM0Y\
89N1P0dakfWACUQrj46dvpDmaQtomjIPK5QABEIIgJPFci0dQlXA6Pa5NLTPYUz7XEKVyYOFNfLJIeyShS11rS3ngVTW1/2Xz+JrA0IyZvX9WI6FMvDbRx/vT5/4ed9wB2kh+aPzh5IQ38t8B9wnpBhblpNc1osUlImefF6gjQZ8Tr32Jtr3MI\
Dx/S+H3FmyKQIRShVlSeTglV4/cxmMDpeRCBgwQCZ9LZZJ94Lxi1+uDd94ojxoGr//YgnE6FysMJeD5Ymvrz+ROXMGOxydkWxbgvZBKsWVziNke8/c9PBRdpBIsh6jNVJJBrp/n5r3wRhxqiyVkaa6ZiExQkkTqG5yCYaQ4RjSDQ/HXFQs1b1D\
L5xgiMrqKmLJBBW1dQgpi6FkUslUJbLBSJflxt8xviZ3+cL22pHzSVTNgdzf95tcJkO6J8BAX4Tei5eeNVrbKpg8HErNOl7WTwYuWeQzsS0A0nU2mXB8qqpMIdR1LSdSfMYAlOsgbZtE6zRGzJzVKqR8DsBJzHncrb2j/BCLN46mpmksdjC8oS\
g3h3CmF5IAodRyKpt3jwNenfTi9on1y1agXAcrGEEF4pOBPsCEolOfGTl+C7WNGyjLyfpjx7ABrc3Lu+fNbUmfP/cYJvcNyG1C2buldanHy547GaiZtC57Pk3vj10grIj2sht1vv95ACtY/VbLys+3W66Fn9MlIaVj5W3AGSIc00z36VObgV1F\
OyIUh4ynO5yq1nSuuzMCtAkplxtdAttqR5q2TV5/GmGBzsO3O/5i4fSwpqV9D+Al5VYeAZ7ysz2rjMdSYGmuu3NYRDTKdt+TbnJnvv9sB9rDy4C0CyRlOblhBpxoJ8J5yM/27BXSno/xxxqjw0KoQYToMtr7QtqB71UgQr7/5jjif3Ml+nMAPW\
0KcJFMcOUAAAAASUVORK5CYII='

warning_sign = BytesIO(b64decode(_warning_sign_b64))
refresh_sign = BytesIO(b64decode(_refresh_sign_b64))
help_sign = BytesIO(b64decode(_help_sign_b64))
info_sign = BytesIO(b64decode(_info_sign_b64))