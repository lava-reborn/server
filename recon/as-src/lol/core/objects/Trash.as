class lol.core.objects.Trash extends lol.core.objects.Heapable
{
   var dam_mod;
   var getProp;
   var name;
   var range_mod;
   var setProp;
   var st_mod;
   var sub_name;
   static var MOD_ARR;
   static var className = "Trash";
   var __className = "Trash";
   function Trash(ID, _typeID, _rooID)
   {
      super(ID,_typeID,_rooID);
      lol.core.objects.Trash.MOD_ARR = new Array();
      lol.core.objects.Trash.MOD_ARR["0"] = "Кустарное";
      lol.core.objects.Trash.MOD_ARR["1"] = "Старое";
      lol.core.objects.Trash.MOD_ARR["2"] = "Обычное";
      lol.core.objects.Trash.MOD_ARR["3"] = "Заводское";
      lol.core.objects.Trash.MOD_ARR["4"] = "Идеальное";
      lol.core.objects.Trash.MOD_ARR["0M"] = "Кустарный";
      lol.core.objects.Trash.MOD_ARR["1M"] = "Старый";
      lol.core.objects.Trash.MOD_ARR["2M"] = "Обычный";
      lol.core.objects.Trash.MOD_ARR["3M"] = "Заводской";
      lol.core.objects.Trash.MOD_ARR["4M"] = "Идеальный";
      lol.core.objects.Trash.MOD_ARR["0F"] = "Кустарная";
      lol.core.objects.Trash.MOD_ARR["1F"] = "Старая";
      lol.core.objects.Trash.MOD_ARR["2F"] = "Обычная";
      lol.core.objects.Trash.MOD_ARR["3F"] = "Заводская";
      lol.core.objects.Trash.MOD_ARR["4F"] = "Идеальная";
      lol.core.objects.Trash.MOD_ARR.BP = "Чертеж";
   }
   function initialize(obj)
   {
      super.initialize(obj);
      this.range_mod = obj.range_mod;
      this.st_mod = obj.st_mod;
      this.dam_mod = obj.dam_mod;
   }
   function set _name(value)
   {
      var _loc3_ = value.indexOf("$",0);
      var _loc4_;
      if(_loc3_ != -1)
      {
         _loc4_ = value.substr(_loc3_ + 1,value.length);
         this.setProp("sub_name",lol.core.objects.Trash.MOD_ARR[_loc4_]);
         this.sub_name = lol.core.objects.Trash.MOD_ARR[_loc4_];
         value = value.substr(0,_loc3_);
      }
      this.name = value;
   }
   function get rangeMod()
   {
      return this.getProp("range_mod");
   }
   function set rangeMod(tRangeMod)
   {
      this.setProp("range_mod",tRangeMod);
   }
   function get staminaMod()
   {
      return this.getProp("st_mod");
   }
   function set staminaMod(tStaminaMod)
   {
      this.setProp("st_mod",tStaminaMod);
   }
   function get damageMod()
   {
      return this.getProp("dam_mod");
   }
   function set damageMod(tDamMod)
   {
      this.setProp("dam_mod",tDamMod);
   }
}
