class lol.services.GameEvents
{
   static var eventsArr;
   static var WAR_STATE_START = 0;
   static var WAR_STATE_END = 1;
   static var MISS = 2;
   static var DAMAGE = 3;
   static var CRITICAL_DAMAGE = 4;
   static var HEAL = 5;
   static var REGENERATE_STAMINA = 6;
   static var REGENERATE_HEALTH = 7;
   static var RELOAD = 8;
   static var DIE = 9;
   static var RESPAM = 10;
   static var BREAK = 11;
   static var UNLOAD_FIREARM = 12;
   static var NEW_PLAYER = 13;
   static var LOST_PLAYER = 14;
   static var USE = 15;
   static var GET_LOOT = 16;
   static var ATTRIBTE_UP = 17;
   static var SKILL_UP = 18;
   static var SPEC_UP = 19;
   static var LOST_ITEM = 20;
   static var GET_ITEM = 21;
   static var NEW_QUEST = 22;
   static var CANCEL_QUEST = 23;
   static var QUEST_COMPLETE = 24;
   static var BUY = 25;
   static var SELL = 26;
   static var SUMMARY_DAMAGE = 27;
   static var CA_DAMAGE = 28;
   static var _ref = new lol.services.GameEvents();
   function GameEvents()
   {
      lol.events.LEventDispatcher.initialize(this);
      this.createEventsArr();
   }
   function createEventsArr()
   {
      lol.services.GameEvents.eventsArr = new Array();
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.WAR_STATE_START] = ["В локации начался бой","#151515"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.WAR_STATE_END] = ["В локации закончился бой","#151515"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.MISS] = ["Персонаж &nickname& промахивается"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.DAMAGE] = ["Персонаж &nickname& выстрелил по персонажу &nickname2& и нанес вред &health_damage&&stamina_damage& при помощи &itemname&","#151515","#615e4e","nickname2"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.SUMMARY_DAMAGE] = ["Персонаж &nickname& произвел по персонажу &nickname2& &value& выстрелов и нанес вред &health_damage&&stamina_damage& при помощи &itemname&","#151515","#615e4e","nickname2"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.CA_DAMAGE] = ["Персонаж &nickname& наносит вред персонажу &nickname2& &health_damage&&stamina_damage& при помощи &itemname&","#151515","#615e4e","nickname2"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.CRITICAL_DAMAGE] = ["Персонаж &nickname& наносит персонажу &nickname2& критический вред &health_damage&&stamina_damage& при помощи &itemname&","#151515","#615e4e","nickname2"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.HEAL] = ["Персонаж &nickname& восстанавливает &health_inc&&stamina_inc& при помощи &itemname&","#151515","#58732d","nickname2"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.REGENERATE_STAMINA] = ["Персонаж &nickname& восстанавливает &value& единиц выносливости","#151515","#58732d","nickname"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.REGENERATE_HEALTH] = ["Персонаж &nickname& восстанавливает &value& единиц здоровья","#151515","#58732d","nickname"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.RELOAD] = ["Персонаж &nickname& перезаряжает &value&","#151515"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.DIE] = ["Персонаж &nickname& падает замертво","#151515","#615e4e","nickname2"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.RESPAM] = ["Персонаж &nickname& поднимается едва живой","#00007D"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.BREAK] = ["Ваш предмет &itemname& сломан","#615e4e"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.UNLOAD_FIREARM] = ["Ваше оружие &itemname& разряжено","#615e4e"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.NEW_PLAYER] = ["Персонаж &nickname& появляется в &locationname&","#151515"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.LOST_PLAYER] = ["Персонаж &nickname& покидает локацию &locationname&","#151515"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.USE] = ["Персонаж &nickname& применяет предмет","#151515"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.GET_LOOT] = ["Персонаж &nickname& поднимает предмет","#151515"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.ATTRIBTE_UP] = ["Атрибут увеличен до &value&","#00007D"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.SKILL_UP] = ["Навык увеличен до &value&","#00007D"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.SPEC_UP] = ["Специализация увеличена до &value&","#00007D"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.LOST_ITEM] = ["Вами потерян предмет &itemname&","#00007D"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.GET_ITEM] = ["Вами получен предмет &itemname&","#00007D"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.NEW_QUEST] = ["Вами получен квест &quest_name&","#00007D"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.CANCEL_QUEST] = ["Вы отказались от квеста &quest_name&","#00007D"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.QUEST_COMPLETE] = ["Квест &quest_name& завершен","#00007D"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.BUY] = ["Вы купили &value& шт. <B>[&itemname&]</B> и потратили &value2&","#a5a631"];
      lol.services.GameEvents.eventsArr[lol.services.GameEvents.SELL] = ["Вы продали &value& шт. <B>[&itemname&]</B> и получили &value2&","#a5a631"];
   }
   static function addEvent(id, obj)
   {
      var _loc1_;
      var _loc4_;
      var _loc5_;
      var _loc7_;
      var _loc3_;
      if(lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_EVENT_CHANNEL))
      {
         _loc1_ = lol.services.GameEvents.parseString(lol.services.GameEvents.eventsArr[id][0],obj);
         if(lol.services.GameEvents.eventsArr[id][3])
         {
            _loc4_ = lol.core.Master.getInstance().gamer.playerInfo.name;
            _loc5_ = obj[lol.services.GameEvents.eventsArr[id][3]];
            if(_loc5_ == _loc4_)
            {
               _loc1_ = "<font color=\"" + lol.services.GameEvents.eventsArr[id][2] + "\">" + _loc1_ + "</font>";
            }
            else
            {
               _loc1_ = "<font color=\"" + lol.services.GameEvents.eventsArr[id][1] + "\">" + _loc1_ + "</font>";
            }
         }
         else
         {
            _loc1_ = "<font color=\"" + lol.services.GameEvents.eventsArr[id][1] + "\">" + _loc1_ + "</font>";
         }
         _loc7_ = new Object();
         _loc7_.group = lol.core.Chat.CHAT_EVENT_CHANNEL;
         _loc7_.from = "events";
         _loc7_.entry = _loc1_;
         _loc3_ = lol.core.Master.getInstance().chat;
         if(_loc3_ != undefined)
         {
            _loc3_.userMsg({param:_loc7_});
         }
         else
         {
            trace("Master.getInstance().chat == undefined");
         }
      }
   }
   static function parseString(mess, obj)
   {
      var _loc5_ = "";
      var _loc3_ = false;
      var _loc4_ = "";
      var _loc2_ = 0;
      var _loc1_;
      while(_loc2_ < mess.length)
      {
         _loc1_ = mess.charAt(_loc2_);
         if(_loc3_)
         {
            if(_loc1_ != "&")
            {
               _loc4_ += _loc1_;
            }
            else
            {
               _loc5_ += lol.services.GameEvents.getProp(_loc4_,obj);
               _loc3_ = false;
               _loc4_ = "";
            }
         }
         else if(_loc1_ == "&")
         {
            _loc3_ = true;
         }
         else
         {
            _loc5_ += _loc1_;
         }
         _loc2_ = _loc2_ + 1;
      }
      return _loc5_;
   }
   static function getProp(str, obj)
   {
      var _loc3_ = "";
      var _loc6_;
      var _loc4_;
      var _loc5_;
      if(str == "nickname" || str == "nickname2")
      {
         _loc3_ = lol.services.GameEvents.parseNamePers(obj[str]);
      }
      else if(str == "value" || str == "locationname" || str == "value2")
      {
         _loc3_ = obj[str];
      }
      else if(str == "itemname")
      {
         _loc6_ = obj[str];
         _loc3_ = _loc6_.getProp("name");
      }
      else if(str == "health_damage")
      {
         if(obj[str] != 0)
         {
            _loc3_ = obj[str] + " по здоровью";
         }
      }
      else if(str == "stamina_damage")
      {
         if(obj[str] != 0)
         {
            if(obj.health_damage != 0)
            {
               _loc3_ = " и ";
            }
            _loc3_ += obj[str] + " по выносливости";
         }
      }
      else if(str == "health_inc")
      {
         _loc3_ = obj[str] + " единиц здоровья";
         _loc4_ = lol.core.player.Gamer.ID;
         _loc5_ = obj.nickname2;
         if(_loc4_ != _loc5_)
         {
            _loc3_ += " игроку " + obj.nickname2;
         }
      }
      else if(str == "stamina_inc")
      {
         if(obj.health_inc != 0)
         {
            _loc3_ = " и " + obj[str];
         }
         _loc3_ += obj[str] + " единиц выносливости";
      }
      return _loc3_;
   }
   static function parseNamePers(name)
   {
      var _loc2_ = name.indexOf("<br>");
      var _loc1_ = lol.utils.ParseString.replaceAll(name,"<br>","&lt;");
      if(_loc2_ != -1)
      {
         _loc1_ += "&gt;";
      }
      return _loc1_;
   }
}
