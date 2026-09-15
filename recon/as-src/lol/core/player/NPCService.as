class lol.core.player.NPCService
{
   function NPCService()
   {
   }
   static function getServiceList(id)
   {
      var _loc3_ = lol.core.Master.getInstance().getPlayer(id);
      var _loc2_;
      var _loc1_;
      if(_loc3_ instanceof lol.core.player.NPC)
      {
         _loc2_ = lol.core.player.NPC(_loc3_);
         _loc1_ = new Array();
         if(_loc2_ instanceof lol.core.player.Trader)
         {
            _loc1_.push("trade");
         }
         if(_loc2_ instanceof lol.core.player.Upgrader)
         {
            _loc1_.push("upgrade");
         }
         if(_loc2_ instanceof lol.core.player.Teacher)
         {
            _loc1_.push("spec");
         }
         if(_loc2_.hasAvailableQuests())
         {
            _loc1_.push("quests");
         }
         if(_loc2_.haveSupport())
         {
            _loc1_.push("support");
         }
         if(_loc2_.canBanking)
         {
            _loc1_.push("bank");
         }
         if(_loc2_.canRepair)
         {
            _loc1_.push("repair");
         }
         if(_loc2_.canTrophy)
         {
            _loc1_.push("regTrophy");
         }
         return _loc1_;
      }
      return null;
   }
   static function openService(id)
   {
      var _loc4_ = lol.core.Master.getInstance().getPlayer(id);
      var _loc3_;
      var _loc2_;
      var _loc1_;
      if(_loc4_ instanceof lol.core.player.NPC)
      {
         _loc3_ = lol.core.player.NPC(_loc4_);
         _loc2_ = new Array();
         if(_loc3_ instanceof lol.core.player.Trader)
         {
            if(_loc3_.canTrade)
            {
               _loc2_.push("trade");
               if(!_loc1_)
               {
                  _loc1_ = "trade";
               }
            }
            if(_loc3_.canRepair)
            {
               _loc2_.push("repair");
               if(!_loc1_)
               {
                  _loc1_ = "repair";
               }
            }
            if(_loc3_.canTrophy)
            {
               _loc2_.push("regTrophy");
               if(!_loc1_)
               {
                  _loc1_ = "regTrophy";
               }
            }
         }
         else if(_loc3_ instanceof lol.core.player.Upgrader)
         {
            _loc2_.push("upgrade");
            _loc1_ = "upgrade";
         }
         else if(_loc3_ instanceof lol.core.player.Lessor)
         {
            _loc2_.push("transRent");
            _loc1_ = "transRent";
         }
         else if(_loc3_ instanceof lol.core.player.Teacher)
         {
            _loc2_.push("spec");
            _loc1_ = "spec";
         }
         else if(_loc3_.haveSupport())
         {
            _loc2_.push("support");
            _loc1_ = "support";
         }
         else if(_loc3_ instanceof lol.core.player.Auctioner)
         {
            _loc2_.push("auction");
            _loc2_.push("auctionMyLots");
            _loc1_ = "auction";
         }
         if(_loc3_.canBanking)
         {
            _loc2_.push("bank");
            if(!_loc1_)
            {
               _loc1_ = "bank";
            }
         }
         if(_loc3_.hasAvailableQuests())
         {
            _loc2_.push("quests");
            _loc1_ = "quests";
         }
         if(_loc2_.length > 0)
         {
            lol.core.SceneShifter.openNewWindow(_loc1_,undefined,_loc2_);
         }
      }
   }
}
