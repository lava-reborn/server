class lol.gpui.ExtListItemContainer extends lol.gpui.ExtItemContainer
{
   var bg_mc;
   var item;
   function ExtListItemContainer()
   {
      super();
      this.btnLinkID = "list_info_btn";
   }
   function attachBack(bID)
   {
      var _loc2_;
      switch(bID)
      {
         case lol.core.objects.Item.HEAL_ITEM:
            _loc2_ = "list_medikKitBG";
            break;
         case lol.core.objects.Item.FIRE_ARM:
            _loc2_ = "list_fireArmBG";
            break;
         case lol.core.objects.Item.AMMO:
            _loc2_ = "list_ammoBG";
            break;
         case lol.core.objects.Item.TRASH:
            _loc2_ = "list_trashBG";
            break;
         case lol.core.objects.Item.QUEST:
            _loc2_ = "list_questBG";
            break;
         case lol.core.objects.Item.TROPHY:
            _loc2_ = "list_trophyBG";
            break;
         case lol.core.objects.Item.WEAR:
            _loc2_ = "list_wearBG";
            break;
         case lol.core.objects.Item.COLD_ARM:
            _loc2_ = "list_fireArmBG";
      }
      var _loc3_ = this.item.getProp("premium");
      var _loc4_;
      if(_loc3_ == 1 || _loc3_ == 2)
      {
         _loc2_ += "_premium";
      }
      else
      {
         _loc4_ = this.item.getProp("g_cost");
         if(_loc4_)
         {
            _loc2_ += "_gold";
         }
      }
      this.bg_mc.attachMovie(_loc2_,"bg",0);
   }
}
