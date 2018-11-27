# Outboard
Outboard is meant as an additional security guard, his features are very specific and tailored for a few specific servers. Don't expect this to be an all around moderation bot

## Raids
Outboard has 2 raid triggers:
- 5 people joining in less then 30 seconds
- 10 people joining in less then 60 seconds

A few things will happen if the alarm is set off:
1) The raid is assigned an ID for future reference
2) Reinforcements are called in (firing pre-configured message)
3) A raid control panel is provided
4) All raiders are welcomed a very special, exclusive role (some people keep referring to this as the mute role for some reason)
5) The other servers are notified a raid is going on
6) Anyone joining while the alarm is still active will also get the role and considered part of the raid

The alarm is turned off after nobody joins for 2 minutes or the raid is dismissed as false alarm. The other servers will also be informed the raid has ended.


So where do the moderators come in? Good question
They come in whenever they have time to deal with it, they can fishing their nap, drink their tea, ..., no problem.
Cause all they really have to do is click a button, there are 3 options:
- ban the raiders
- kick the raiders
- dismiss the raid as false alarm

In the last case the raid is instantly terminated, regardless of the 2 minute timer, and the role will be removed from those involved again.

Once the alarm ends, the dashboard will stop working. But don't let that stop you from finishing your tea while it's still hot. If the raid is ended by the 2 minute timer instead of being dismissed, then the role isn't removed.
Once the raid has ended, you can use the ``raid_act`` command to still act on that raid, like with the dasboard, the subcommands are ``ban``, ``kick`` and ``dismiss`` and take a raid id as argument. They work the exact same as during the raid.
So for example ``!raid_act ban 5`` will ban all raiders involved in the raid with ID 5.

To go along with this there is the ``raid_info`` command to get info about a past raid. Options are ``pretty``, ``ids`` and ``raw``, takes a raid ID just like ``raid_act``
For example ``!raid_info ids 5`` will give you all the userIDs of the raids involved in raid 5

Note both the ``raid_act`` and ``raid_info`` commands can be used on other servers then where the raid happened, but it applies to the guild you run it on
So if you run ``raid_act ban 5`` on another server then the one the raid took place, it will ban those raiders in that server


## Bad usernames
Next to that he also is on the lookout for people with bad usernames (checks when people join or change their user/nick name).

The list of bad names is separate per server.

Configuring this list is done with the ``blacklist`` command.

``blacklist add`` will add something to the list (``!blacklist add this is an offencive name`` will add ``this is an offencive name`` to the list)
If you later want to remove something just replace ``add`` with ``remove`` (``!blacklist remove this is an offencive name``)

Validating matches can be done with ``blacklist check`` (``!blacklist check this is my name`` will show what in ``this is my name`` is blacklisted)

When someone joins, changes their username or their nickname, their name will be checked (after 2 seconds and if there currently is no raid going on).
When a name is caught by the filter it will ask with that do with it (similar to a raid), this time the options are:
- Ban the user
- Kick the user
- Remove their nickname
- Set a new nickname (in this case your next message will be their new nickname)

In case of a false positive match you can just ignore it and not click any of the reactions. If it happens too ofter you might want to revise your blacklist entries.