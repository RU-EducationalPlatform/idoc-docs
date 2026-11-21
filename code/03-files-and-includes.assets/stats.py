# small helpers, two named regions

# @snip(mean)
def mean(xs):
    return sum(xs) / len(xs)
# @endsnip(mean)

# @snip(spread)
def spread(xs):
    return max(xs) - min(xs)
# @endsnip(spread)

print(mean([2, 4, 6]), spread([2, 4, 6]))
