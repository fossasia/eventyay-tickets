=== Juiz Last Tweet Widget ===
Contributors: CreativeJuiz
Donate link: https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=P39NJPCWVXGDY&lc=FR&item_name=Juiz%20Last%20Tweet%20Widget%20%2d%20WordPress%20Plugin&currency_code=EUR&bn=PP%2dDonationsBF%3abtn_donateCC_LG%2egif%3aNonHostedGuest
Tags: twitter, widget, social, sidebar, last, tweet
Requires at least: 3.0.1
Tested up to: 3.3.1
Stable tag: 1.0.2

Add a widget to your sidebar to show your latest tweet(s) without JavaScript!

== Description ==

Add a widget to your sidebar to show your latest tweet(s) without JavaScript!

This sidebar's widget offer you the possibility to show your last tweet(s) (THE last by default) in your WordPress web site.
The advantage of this plugin is the absence of JavaScript script to load tweets from twitter : a very good point for your page speed.
Another advantage is the possibility to use a cache system with an adjustable period.
You also can show your avatar and customize the CSS.

**Features**

In admin :

* Easy to install.
* Panel for easy configuration (Appearance -> Widgets).
* Show or hide your avatar
* Default CSS can be disabled or customized
* Adjustable period for cache system

In your site :

* Smart default style (CSS)
* Display link (with special CSS classes) for hastags, users, and web link (`nofollow` links)
* Display twitter's user link and statut's link
* Display source (web, Tweetdeck, etc.) when it's possible


**Languages**

* English
* German
* Spannish
* French


-------------
Français
----

Ajoute un widget à votre site pour lister vos derniers tweets, sans JavaScript !

Ce widget de sidebar vous offre la possibilité d'afficher vos derniers tweets (LE dernier par défaut) dans votre site WordPress.
L'avantage de ce plugin est l'absence de JavaScript pour charger les tweets depuis Twitter : un très bon point pour la vitesse de vos pages.
Un autre avantage est la possibilie d'utiliser un système de cache avec une durée ajustable.
Vous pouvez également afficher votre avatar et personnaliser les CSS.

**Fonctionnalités**

Dans l'administration :

* Facile à installer.
* Panneau facile à configurer (Apparence -> Widgets).
* Affichez ou cachez votre avatar
* Styles par défaut personnalisable (peuvent être simplement désactivé ou écrasés)
* Durée du cache ajustable

In your site :

* Styles par défaut sobres et classes (CSS)
* Affiche les liens (avec des classes spéciales) pour les hastags, utilisateurs, et liens classiques (liens en `nofollow`)
* Affiche un lien vers le statut et le compte twitter
* Affiche la source du tweet (web, Tweetdeck, etc.) quand c'est possible


**Langages**

* Anglais
* Allemand
* Espagnol
* Français

== Installation ==

You can use one of the both method :

**Installation via your Wordpress website**

1. Go to the admin menu 'Plugins' -> 'Install' and search for 'Juiz last tweet'
1. Click 'install' and activate it
1. Configure your widget in Appearance -> Widgets

**Manual Installation**

1. Upload folder `juiz-last-tweet-widget` to the `/wp-content/plugins/` directory.
1. Activate the plugin through the 'Plugins' menu in WordPress.
1. Configure plugin in Appearance -> Widgets.

== Screenshots ==
1. Juiz Last Tweet in action (french interface)
2. Juiz Last Tweet in the admin
3. Juiz Last Tweet with avatar displayed

== Frequently Asked Questions ==

= Why the widget show me an error of load for my tweets ? =
Try to visit the link : http://api.twitter.com/1/statuses/user_timeline.rss?screen_name=USERNAME&count=2 by replacing "USERNAME" with your own username.
If nothing happens, try with : http://search.twitter.com/search.rss?q=from%3AUSERNAME&rpp=2
If nothing happens, it's the fault of Twitter API limitation.

If this link show your 2 last tweets, it's the fault of my script, so contact me.

== Changelog ==

= 1.0.2 =
* Bug fix for cache system (now uses the WP cache ssystem)

= 1.0.1 =
* Bug fix for Twitter API limitation
* Bug fix for disabling default CSS
* You can now show your avatar

= 1.0.0 =
* Bug fix for initial cache
* Bug fix for empty pseudo

= 1.0.0 beta =
* Initial Release, beta.

== Informations ==

Another plugin :
* [Juiz Smart Mobile Admin](http://wordpress.org/extend/plugins/juiz-smart-mobile-admin/ "Your blog always with you")

You like it and want to donate for this plugin ?
Thank you !
[Donate](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=P39NJPCWVXGDY&lc=FR&item_name=Juiz%20Last%20Tweet%20Widget%20%2d%20WordPress%20Plugin&currency_code=EUR&bn=PP%2dDonationsBF%3abtn_donateCC_LG%2egif%3aNonHostedGuest "Donate to this WordPress plugin")

== Upgrade Notice ==

= 1.0.2 =
Upgrade if you tweets, tweets and tweets again and again

= 1.0.1 =
Need upgrade

= 1.0.0 =
No need to upgrade if your tweets are displayed.

= 1.0.0 beta =
New version in test...
