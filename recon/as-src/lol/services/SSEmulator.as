class lol.services.SSEmulator
{
   static var PATHTYPE;
   static var localPath = "";
   static var LOCAL = 0;
   static var WEB = 1;
   static var DEBUG = "false";
   static var BASE = "_BASE_";
   static var SOUND = "_SOUND_";
   static var TYPE = "_TYPE_";
   static var PERS = "_PERS_";
   static var VARIANT = "_VARIANT_";
   static var ID = "_ID_";
   static var PERSNAME = "_PERSNAME_";
   static var ACTION = "_ACTION_";
   function SSEmulator()
   {
   }
   static function getGMTURL(x, y, type)
   {
      var _loc2_;
      var _loc4_;
      var _loc1_;
      if(type == lol.core.globmap.DisplayLandscape.FULL)
      {
         _loc4_ = 256;
         _loc1_ = "globalmap/full/";
      }
      else
      {
         _loc4_ = 32;
         _loc1_ = "globalmap/client/";
      }
      var _loc3_ = String(y * _loc4_ + x);
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc2_ = lol.core.SSettings.getInstance().base + "/" + _loc1_ + _loc3_ + ".jpg";
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc2_ = lol.services.SSEmulator.localPath + _loc1_ + _loc3_ + ".jpg";
      }
      return _loc2_;
   }
   static function getLocDescription(locID)
   {
      var _loc1_;
      _loc1_ = "locations/static/" + locID + ".xml";
      var _loc4_ = lol.local.SBase.getInstance().getLocDef(_loc1_);
      var _loc6_;
      var _loc5_;
      var _loc3_;
      if(!_loc4_)
      {
         if(locID >> 28 == 4)
         {
            _loc1_ = "locations/deadloc/" + (locID >> 26 & 3) + ".xml";
         }
         else if(locID >> 26 == 0)
         {
            _loc6_ = locID >> 13;
            _loc5_ = locID & 0x1FFF;
            _loc3_ = (_loc6_ + _loc5_ & 3) + 1;
            _loc1_ = "locations/desert/" + lol.utils.ParseString.strPad(_loc3_,"0",4,lol.utils.ParseString.STR_PAD_LEFT) + ".xml";
         }
         else
         {
            _loc1_ = "";
         }
      }
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc1_ = lol.core.SSettings.getInstance().base + "/" + _loc1_;
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc1_ = lol.services.SSEmulator.localPath + _loc1_;
      }
      return _loc1_;
   }
   static function getLocLibraryURL(locID)
   {
      var _loc1_;
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc1_ = lol.core.SSettings.getInstance().base + "/locations/libs/" + locID + ".swf";
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc1_ = lol.services.SSEmulator.localPath + "locations/libs/" + locID + ".swf";
      }
      return _loc1_;
   }
   static function getSpriteURL(type, id)
   {
      var _loc1_;
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc1_ = lol.core.SSettings.getInstance().base + "/locations/libs/" + type + "/" + id + ".swf";
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc1_ = lol.services.SSEmulator.localPath + "locations/libs/" + type + "/" + id + ".swf";
      }
      return _loc1_;
   }
   static function getNewspaperURL()
   {
      var _loc1_;
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc1_ = lol.core.SSettings.getInstance().base + "/lib/newspaper/issue.jpg";
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc1_ = "lib/newspaper/issue.jpg";
      }
      return _loc1_;
   }
   static function getHelpURL()
   {
      var _loc1_;
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc1_ = lol.core.SSettings.getInstance().base + "/lib/help/videohelp.swf";
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc1_ = "lib/help/videohelp.swf";
      }
      return _loc1_;
   }
   static function getHelpXmlURL()
   {
      var _loc1_;
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc1_ = lol.core.SSettings.getInstance().base + "/xmldocs/help.xml";
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc1_ = "xmldocs/help.xml";
      }
      return _loc1_;
   }
   static function getLoacNameXmlURL()
   {
      var _loc1_;
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc1_ = lol.core.SSettings.getInstance().base + "/database/locations.xml";
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc1_ = lol.services.SSEmulator.localPath + "database/locations.xml";
      }
      return _loc1_;
   }
   static function getIntroURL()
   {
      var _loc1_;
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc1_ = lol.core.SSettings.getInstance().base + "/lib/intro/intro.swf";
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc1_ = "lib/intro/intro.swf";
      }
      return _loc1_;
   }
   static function getSpecXmlURL()
   {
      var _loc1_;
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc1_ = lol.core.SSettings.getInstance().base + "/xmldocs/spec.xml";
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc1_ = "xmldocs/spec.xml";
      }
      return _loc1_;
   }
   static function getStringURL()
   {
      var _loc1_;
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc1_ = lol.core.SSettings.getInstance().base + "/database/texts.xml";
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc1_ = lol.services.SSEmulator.localPath + "database/texts.xml";
      }
      return _loc1_;
   }
   static function getRandom()
   {
      var _loc1_ = Math.round(Math.random() * 10000000000000);
      return _loc1_;
   }
   static function getSoundURL(name, type)
   {
      var _loc1_;
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc1_ = lol.core.SSettings.getInstance().base + "/sounds/" + type + "/" + name + ".swf";
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc1_ = lol.services.SSEmulator.localPath + "sounds/" + type + "/" + name + ".swf";
      }
      return _loc1_;
   }
   static function loadDefault()
   {
      var _loc1_ = lol.display.SourceLibrary.getSource("default");
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc1_.loadSource(lol.core.SSettings.getInstance().base + "/personages/default/ghost_0_0.swf");
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc1_.loadSource(lol.services.SSEmulator.localPath + "personages/default/ghost_0_0.swf");
      }
   }
   static function getPersInfoURL(persname)
   {
      var _loc1_;
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc1_ = lol.core.SSettings.getInstance().base + "/personages/" + persname + ".xml";
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc1_ = lol.services.SSEmulator.localPath + "personages/" + persname + ".xml";
      }
      return _loc1_;
   }
   static function getPersAnimURL(persname, action_id)
   {
      var _loc1_;
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc1_ = lol.core.SSettings.getInstance().base + "/personages/" + persname + "/" + persname + "_" + action_id + ".swf";
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc1_ = lol.services.SSEmulator.localPath + "personages/" + persname + "/" + persname + "_" + action_id + ".swf";
      }
      return _loc1_;
   }
   static function getMobInfoURL(mobname)
   {
      var _loc2_;
      var _loc1_ = lol.local.SBase.getInstance().getMob(mobname);
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc2_ = lol.core.SSettings.getInstance().base + "/mobs/" + _loc1_.resource + ".xml";
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc2_ = lol.services.SSEmulator.localPath + "mobs/" + _loc1_.resource + ".xml";
      }
      return _loc2_;
   }
   static function getMobAnimURL(mobname, action_id)
   {
      var _loc2_;
      var _loc1_ = lol.local.SBase.getInstance().getMob(mobname);
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc2_ = lol.core.SSettings.getInstance().base + "/mobs/" + _loc1_.resource + "/" + _loc1_.resource + "_" + action_id + ".swf";
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc2_ = lol.services.SSEmulator.localPath + "mobs/" + _loc1_.resource + "/" + _loc1_.resource + "_" + action_id + ".swf";
      }
      return _loc2_;
   }
   static function getItemAnimURL(persname, action_id, primSlotType, primSlotRootType)
   {
      var _loc1_;
      var _loc2_ = lol.services.SSEmulator.getFolderName(primSlotRootType);
      action_id = lol.utils.ParseString.replace(action_id,"_","_0_",0);
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc1_ = lol.core.SSettings.getInstance().base + "/classes/" + _loc2_ + action_id + ".swf";
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc1_ = lol.services.SSEmulator.localPath + "classes/" + _loc2_ + action_id + ".swf";
      }
      return _loc1_;
   }
   static function getIcon(typeID)
   {
      var _loc1_;
      var _loc2_ = lol.local.SBase.getInstance().getItem(typeID);
      _loc1_ = "classes/";
      _loc1_ += lol.services.SSEmulator.getFolderName(_loc2_.rootID);
      _loc1_ += _loc2_.name + "/ico.swf";
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc1_ = lol.core.SSettings.getInstance().base + "/" + _loc1_;
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc1_ = lol.services.SSEmulator.localPath + _loc1_;
      }
      return _loc1_;
   }
   static function getTransportIcon(typeID)
   {
      var _loc1_;
      var _loc3_ = lol.local.SBase.getInstance().getItem(typeID);
      _loc1_ = "transport/" + typeID + ".swf";
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc1_ = lol.core.SSettings.getInstance().base + "/" + _loc1_;
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc1_ = lol.services.SSEmulator.localPath + _loc1_;
      }
      return _loc1_;
   }
   static function getEffectIcon(typeID)
   {
      var _loc1_;
      _loc1_ = "effects/" + typeID + ".swf";
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc1_ = lol.core.SSettings.getInstance().base + "/" + _loc1_;
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc1_ = lol.services.SSEmulator.localPath + _loc1_;
      }
      return _loc1_;
   }
   static function getBG_DescURL()
   {
      var _loc1_;
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc1_ = lol.core.SSettings.getInstance().base + "/xmldocs/battlegrounds.xml";
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc1_ = "xmldocs/battlegrounds.xml";
      }
      trace("getBG_DescURL -> " + _loc1_ + ", PATHTYPE = " + lol.services.SSEmulator.PATHTYPE);
      return _loc1_;
   }
   static function getHintsDescURL()
   {
      var _loc1_ = "hints/hints.xml";
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc1_ = lol.core.SSettings.getInstance().base + "/" + _loc1_;
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc1_ = lol.services.SSEmulator.localPath + _loc1_;
      }
      return _loc1_;
   }
   static function getHintsImage(typeID)
   {
      var _loc1_;
      _loc1_ = "hints/" + typeID + ".swf";
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc1_ = lol.core.SSettings.getInstance().base + "/" + _loc1_;
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc1_ = lol.services.SSEmulator.localPath + _loc1_;
      }
      return _loc1_;
   }
   static function getAvatarInfoURL()
   {
      var _loc1_;
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc1_ = lol.core.SSettings.getInstance().base + "/avatars/list.xml";
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc1_ = lol.services.SSEmulator.localPath + "avatars/list.xml";
      }
      return _loc1_;
   }
   static function getAvatarURL(id, variant)
   {
      var _loc1_;
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc1_ = lol.core.SSettings.getInstance().base + "/avatars/" + id + "_" + variant + ".png";
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         _loc1_ = lol.services.SSEmulator.localPath + "avatars/" + id + "_" + variant + ".png";
      }
      return _loc1_;
   }
   static function getHashURL(session)
   {
      var _loc1_ = "http://www.lava-online.ru/client/game_session.php?session=" + session;
      return _loc1_;
   }
   static function getFolderName(rootID)
   {
      var _loc1_;
      switch(rootID)
      {
         case 0:
            _loc1_ = "FireArm/";
            break;
         case 1:
            _loc1_ = "WearItem/";
            break;
         case 2:
            _loc1_ = "Heal_Item/";
            break;
         case 3:
            _loc1_ = "Ammo/";
            break;
         case 4:
            _loc1_ = "SimpleObject/";
            break;
         case 5:
            _loc1_ = "ColdArm/";
            break;
         case 6:
            _loc1_ = "Trophy/";
            break;
         default:
            _loc1_ = "";
      }
      return _loc1_;
   }
}
