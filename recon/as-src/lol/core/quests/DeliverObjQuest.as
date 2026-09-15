class lol.core.quests.DeliverObjQuest implements lol.core.quests.QuestMission
{
   var finded;
   var item;
   var diFlag = false;
   function DeliverObjQuest()
   {
   }
   function getMissionStatus()
   {
      var _loc2_;
      if(this.item.inited)
      {
         if(this.finded)
         {
            _loc2_ = "предмет " + this.item.getProp("name") + " найден, но не доставлен";
         }
         else
         {
            _loc2_ = "предмет " + this.item.getProp("name") + " не найден";
         }
         return _loc2_;
      }
      return "";
   }
   function initialize(obj)
   {
      obj = obj.param.obj;
      if(obj)
      {
         this.item = lol.core.objects.ItemFactory.createPrototype(obj);
      }
   }
   function update(obj)
   {
      var _loc2_ = new Object();
      _loc2_.itemName = this.item.getProp("name");
      this.finded = obj.param.obj;
      _loc2_.finded = this.finded;
      this.diFlag = true;
      return _loc2_;
   }
   function getDIFlag()
   {
      return this.diFlag;
   }
}
