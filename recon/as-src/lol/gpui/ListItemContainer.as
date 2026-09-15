class lol.gpui.ListItemContainer extends lol.gpui.ItemContainer
{
   var bg_mc;
   function ListItemContainer()
   {
      super();
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
      var _loc6_;
      if(_loc3_ == 1 || _loc3_ == 2)
      {
         _loc2_ += "_premium";
      }
      else
      {
         _loc6_ = this.item.getProp("g_cost");
         if(_loc6_)
         {
            _loc2_ += "_gold";
         }
      }
      this.bg_mc.attachMovie(_loc2_,"bg",0);
      var _loc5_;
      var _loc4_;
      if(this.groupItem)
      {
         _loc5_ = this.bg_mc.attachMovie(_loc2_,"bg",-5);
         _loc4_ = this.bg_mc.attachMovie(_loc2_,"bg",-10);
         _loc5_._x = 5;
         _loc5_._y = 5;
         _loc4_._x = 10;
         _loc4_._y = 10;
      }
   }
}
