class lol.gpui.UserSettings
{
   static var SO;
   static var defaultSettingsArray;
   static var settingsArray;
   static var SHOW_TIME_IN_CHAT = "timeEnabled";
   static var SCROLL_IN_SIDE = "scrollEnabled";
   static var AUTO_RELOAD = "autoReload";
   static var TYPE_OF_LIST_TRADE = "typeOfListTrade";
   static var SORT_MASK_TRADE = "SortMaskTrade";
   static var TYPE_OF_LIST_EQUIP = "typeOfListEquip";
   static var SORT_MASK_EQUIP = "SortMaskEquip";
   static var TYPE_OF_LIST_REPAIR = "typeOfListRepair";
   static var SORT_MASK_REPAIR = "SortMaskRepair";
   static var TYPE_OF_LIST_UPGRADE = "typeOfListUpgrade";
   static var SORT_MASK_UPGRADE = "SortMaskUpgrade";
   static var TYPE_OF_LIST_BARTER = "typeOfListBarter";
   static var SORT_MASK_BARTER = "SortMaskBarter";
   static var TYPE_OF_LIST_LOOT = "typeOfListLoot";
   static var SORT_MASK_LOOT = "SortMaskLoot";
   static var TYPE_OF_LIST_BANK = "typeOfListBank";
   static var SORT_MASK_BANK = "SortMaskBank";
   static var TYPE_OF_LIST_MAIL = "typeOfListMail";
   static var SORT_MASK_MAIL = "SortMaskMail";
   static var TYPE_OF_LIST_AUCTION = "typeOfListAuction";
   static var SORT_MASK_AUCTION = "SortMaskAuction";
   static var CRITICAL_AMMO_ALARM = "criticalAmmoAlarm";
   static var NUMBER_OF_CRITICAL_AMMO = "numberOfCriticalAmmo";
   static var NUMBER_OF_MESSAGE = "numberOfMessage";
   static var SHOW_MSGS_UNDER_HEAD = "showMessagesUnderHead";
   static var SHOW_TRADE_CHANNEL = "showTradeChannel";
   static var SHOW_WORLD_CHANNEL = "showWorldChannel";
   static var SHOW_HELP_CHANNEL = "showHelpChannel";
   static var SHOW_EVENT_CHANNEL = "showEventChannel";
   static var CURRENT_SCILL_CHAR = "currentSkillChar";
   static var SHOW_GRID = "showGrid";
   static var GLOBAL_SCALE = "globalScale";
   static var HOT_KEYS = "hotKeyArr";
   static var MINI_MAP_OPEN = "miniMapOpen";
   static var WEAPON_PAN_OPEN = "weaponPanOpen";
   static var FX_PAN_OPEN = "FXPanOpen";
   static var WATER_ANIMATION = "waterAnimation";
   static var WARNING_MESSAGE = "warningMessage";
   static var AUTO_SHOT = "autoShot";
   static var AUTO_FIRE = "autoFire";
   static var ONLY_ONLINE_MEMBERS = "onlyOnlineMembers";
   static var SORT_CLAN_LIST_BY = "sortClanListBy";
   static var SORT_CLAN_LIST_REVERSE = "sortClanListReverse";
   static var SORT_STANDING_LIST_BY = "sortStandingListBy";
   static var SORT_STANDING_LIST_REVERSE = "sortStandingListReverse";
   static var SORT_MAIL_LIST_BY = "sortMailListBy";
   static var SORT_MAIL_LIST_REVERSE = "sortMailListReverse";
   static var LABEL_OR_PLAYERS = "LABEL_OR_PLAYERS";
   static var PATH_FINDING = "PATH_FINDING";
   static var SERVICE_MESSAGE = "SERVICE_MESSAGE";
   static var ANIMATION = "ANIMATION";
   static var STAND_ANIMATION = "STAND_ANIMATION";
   static var CRUEL_TROPHY = "CRUEL_TROPHY";
   static var FORBID_PARTY_INVITE = "FORBID_PARTY_INVITE";
   static var SHOW_OWN_WEAR_SET = "SHOW_OWN_WEAR_SET";
   static var SHOW_GAME_HELP = "SHOW_GAME_HELP";
   function UserSettings()
   {
   }
   static function init()
   {
      lol.gpui.UserSettings.initDefaultArr();
      lol.gpui.UserSettings.SO = SharedObject.getLocal("csettings","/");
      lol.gpui.UserSettings.settingsArray = lol.gpui.UserSettings.SO.data.settingsArray;
      if(lol.gpui.UserSettings.settingsArray == undefined)
      {
         lol.gpui.UserSettings.settingsArray = new Array();
      }
      lol.gpui.UserSettings.settingsArray[lol.gpui.UserSettings.WATER_ANIMATION] = false;
      lol.gpui.UserSettings.settingsArray[lol.gpui.UserSettings.SCROLL_IN_SIDE] = false;
      lol.gpui.UserSettings.settingsArray[lol.gpui.UserSettings.WARNING_MESSAGE] = false;
   }
   static function initDefaultArr()
   {
      lol.gpui.UserSettings.defaultSettingsArray = new Array();
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SHOW_TIME_IN_CHAT] = true;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SCROLL_IN_SIDE] = false;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.AUTO_RELOAD] = true;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.TYPE_OF_LIST_TRADE] = "icon";
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SORT_MASK_TRADE] = [1,1,1,1,1,1,1,1,0,0];
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.TYPE_OF_LIST_EQUIP] = "icon";
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SORT_MASK_EQUIP] = [1,1,1,1,1,1,1,1,0,0];
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.TYPE_OF_LIST_REPAIR] = "icon";
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SORT_MASK_REPAIR] = [1,1,1,1,1,1,1,1,0,0];
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.TYPE_OF_LIST_UPGRADE] = "icon";
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SORT_MASK_UPGRADE] = [1,1,1,1,1,1,1,1,0,0];
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.TYPE_OF_LIST_BARTER] = "icon";
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SORT_MASK_BARTER] = [1,1,1,1,1,1,1,1,0,0];
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.TYPE_OF_LIST_LOOT] = "icon";
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SORT_MASK_LOOT] = [1,1,1,1,1,1,1,1,0,0];
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.TYPE_OF_LIST_BANK] = "icon";
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SORT_MASK_BANK] = [1,1,1,1,1,1,1,1,0,0];
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.TYPE_OF_LIST_MAIL] = "icon";
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SORT_MASK_MAIL] = [1,1,1,1,1,1,1,1,0,0];
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.TYPE_OF_LIST_AUCTION] = "icon";
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SORT_MASK_AUCTION] = [1,1,1,1,1,1,1,1,0,0];
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.CRITICAL_AMMO_ALARM] = true;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.NUMBER_OF_CRITICAL_AMMO] = 10;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.NUMBER_OF_MESSAGE] = 50;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.CURRENT_SCILL_CHAR] = 0;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SHOW_GRID] = true;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.GLOBAL_SCALE] = "up";
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.WEAPON_PAN_OPEN] = true;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.MINI_MAP_OPEN] = true;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.FX_PAN_OPEN] = true;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.WATER_ANIMATION] = false;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.WARNING_MESSAGE] = false;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.ONLY_ONLINE_MEMBERS] = false;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SORT_CLAN_LIST_BY] = "name";
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SORT_CLAN_LIST_REVERSE] = false;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SORT_STANDING_LIST_BY] = "name";
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SORT_STANDING_LIST_REVERSE] = false;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SORT_MAIL_LIST_BY] = "fullDate";
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SORT_MAIL_LIST_REVERSE] = false;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SHOW_MSGS_UNDER_HEAD] = true;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SHOW_TRADE_CHANNEL] = true;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SHOW_WORLD_CHANNEL] = true;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SHOW_HELP_CHANNEL] = true;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SHOW_EVENT_CHANNEL] = false;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SHOW_OWN_WEAR_SET] = true;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SHOW_GAME_HELP] = true;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.FORBID_PARTY_INVITE] = false;
      lol.gpui.UserSettings.defaultSettingsArray.gameSoundVolume = 50;
      lol.gpui.UserSettings.defaultSettingsArray.interfaceSoundVolume = 50;
      lol.gpui.UserSettings.defaultSettingsArray.musicVolume = 50;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.AUTO_SHOT] = false;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.AUTO_FIRE] = false;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.LABEL_OR_PLAYERS] = "label ";
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.PATH_FINDING] = true;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.SERVICE_MESSAGE] = false;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.ANIMATION] = true;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.STAND_ANIMATION] = false;
      lol.gpui.UserSettings.defaultSettingsArray[lol.gpui.UserSettings.CRUEL_TROPHY] = false;
   }
   static function getSetting(title)
   {
      if(lol.gpui.UserSettings.settingsArray[title] != undefined)
      {
         return lol.gpui.UserSettings.settingsArray[title];
      }
      if(lol.gpui.UserSettings.defaultSettingsArray[title] != undefined)
      {
         return lol.gpui.UserSettings.defaultSettingsArray[title];
      }
      return undefined;
   }
   static function setSetting(title, data)
   {
      if(lol.gpui.UserSettings.settingsArray[title] != undefined)
      {
         delete lol.gpui.UserSettings.settingsArray[title];
         lol.gpui.UserSettings.settingsArray[title] = data;
      }
      else
      {
         lol.gpui.UserSettings.settingsArray[title] = data;
      }
      lol.gpui.UserSettings.flush();
   }
   static function defaultSettings()
   {
      var _loc1_;
      for(var _loc2_ in lol.gpui.UserSettings.defaultSettingsArray)
      {
         _loc1_ = lol.gpui.UserSettings.defaultSettingsArray[_loc2_];
         if(lol.gpui.UserSettings.settingsArray[_loc2_] != undefined)
         {
            delete lol.gpui.UserSettings.settingsArray[_loc2_];
            lol.gpui.UserSettings.settingsArray[_loc2_] = _loc1_;
         }
      }
      lol.gpui.UserSettings.flush();
   }
   static function flush()
   {
      lol.gpui.UserSettings.SO.data.settingsArray = lol.gpui.UserSettings.settingsArray;
      lol.gpui.UserSettings.SO.flush();
   }
   static function clearSharedObject()
   {
      lol.gpui.UserSettings.settingsArray = new Array();
      lol.gpui.UserSettings.flush();
   }
}
