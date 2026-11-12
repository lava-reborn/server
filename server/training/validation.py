"""Training range: validation."""



def integer(value, low, high):
    if isinstance(value, bool):
        raise ValueError('Ожидается целое число')
    n = int(str(value))
    if not low <= n <= high:
        raise ValueError('Значение вне допустимого диапазона')
    return n
