class lol.core.objects.Ammo extends lol.core.objects.Heapable
{
   var __quantity;
   var acc_mod;
   var cost;
   var dam_mod;
   var g_cost;
   var getProp;
   var mod_type;
   var name;
   var piercing;
   var range_mod;
   var setProp;
   var st_mod;
   static var MOD_ARR;
   static var className = "Ammo";
   var __className = "Ammo";
   var BB = "ББ";
   var EK = "ЭК";
   var SB = "СБ";
   var SHK = "ШК";
   var OT = "ОТ";
   var ST = "СТ";
   var KS = "КС";
   var sell_num = 1;
   function Ammo(ID, _typeID, _rooID)
   {
      super(ID,_typeID,_rooID);
   }
   function initialize(obj)
   {
      super.initialize(obj);
      this.range_mod = obj.range_mod;
      this.st_mod = obj.st_mod;
      this.dam_mod = obj.dam_mod;
      this.acc_mod = obj.acc_mod;
      this.piercing = obj.piercing;
      this.sell_num = obj.sell_num;
      this.cost = Math.round(this.cost * 1000 / this.sell_num) / 1000;
      this.g_cost = Math.round(this.g_cost / this.sell_num);
   }
   function set _name(value)
   {
      var _loc3_ = value.indexOf("$",0);
      if(_loc3_ != -1)
      {
         this.mod_type = value.substr(_loc3_ + 1,value.length);
         value = value.substr(0,_loc3_ - 1);
      }
      this.name = value;
   }
   function get quantity()
   {
      return this.__quantity;
   }
   function set quantity(_quantity)
   {
      this.__quantity = _quantity;
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
   function get accMod()
   {
      return this.getProp("acc_mod");
   }
   function set accMod(tAccMod)
   {
      this.setProp("acc_mod",tAccMod);
   }
   function get armorPiercing()
   {
      return this.getProp("piercing");
   }
   function set armorPiercing(tArmorPiercing)
   {
      this.setProp("piercing",tArmorPiercing);
   }
}
