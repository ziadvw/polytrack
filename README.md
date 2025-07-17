# Polymarket Movement Tracker

A tool to quantify and visualize how unpredictable the world is, using price movements from top prediction markets on Polymarket.

# How It Works

Most of the most-watched news and events today are tracked on prediction markets like Polymarket. I initially set out to build something like a “volatility” tracker, to get a sense of how volatile a time period is.

Since market prices represent the odds or probabilities of a certain event happening, if prices are volatile or experience sharp changes over a given time, it means something unexpected happened, or more precisely, something people didn’t predict well. So, what we really want to track is how unpredictable things are; in other words, how big the price changes were.

It’s not actually *“volatility”* in the same sense as we track in normal financial markets, since prediction markets function differently. What we care about is the *absolute value* of price changes, not how volatile the market is in the traditional sense. This gives us a sense of how unpredictable real-world events are, at least those tracked on Polymarket, and more broadly, how volatile or *“crazy”* the world is on any given day.

Initially, I aimed to gather all the markets trading on a given day and weigh them by that day’s *opening open interest (OI)*. I chose open interest because I thought it was a good proxy for how much people cared about a market on that day, more so than the volume traded that day. It’s somewhat analogous to market cap in traditional markets.

The idea was to capture the *opening OI* and multiply it by that day’s price change. I wanted the *opening* OI, rather than the closing, since the end-of-day OI could be impacted by the price changes themselves. This approach would also capture markets that people cared about and where surprising changes happened before the day closed.

The next problem was how to normalize across different days’ open interests. My initial approach was to divide by the total OI of that day’s opening, but it didn’t normalize very well. On days when a particular market made up a large portion of total OI, the index would be disproportionately captured, even if the price change was relatively small.

I then realized that what I actually wanted was to *filter* by the *top N markets* on a given day by OI, not necessarily weigh them. We just want to look at the *top X things people cared about* and see how much they changed. There’s probably no real benefit to weighing those top X markets against each other.

I think this makes more sense now, though I’m open to suggestions. There are probably better ways to normalize by OI. Fortunately, it’s easy to tweak the formula in my library now.

# How to Use

- To backfill active markets for a specific period, use the appropriate flags in the backfill scripts (see `main/backfill.py`).
- You can also backfill scores and experiment with the change formula directly in `backfill.py`.
- All data syncing and updates are automated and run regularly via GitHub Actions.

# Todo
- Tweak formula
  - Deduplicate markets that share same event by highest price change instead of highest OI
- Overlay OI graph on the chart

