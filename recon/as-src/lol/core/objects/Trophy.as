class lol.core.objects.Trophy extends lol.core.objects.Item
{
   var count;
   var getProp;
   var k_id;
   var k_lvl;
   var k_name;
   var name;
   var setProp;
   var time;
   var v_clan;
   var v_id;
   var v_lvl;
   var v_name;
   static var className = "Trash";
   var __className = "Trash";
   function Trophy(ID, _typeID, _rooID)
   {
      super(ID,_typeID,_rooID);
   }
   function initialize(obj)
   {
      super.initialize(obj);
      this.count = obj.count;
      this.k_id = obj.k_id;
      this.k_name = obj.k_name;
      this.k_lvl = obj.k_lvl;
      this.v_id = obj.v_id;
      this.v_name = obj.v_name;
      this.v_lvl = obj.v_lvl;
      this.v_clan = obj.v_clan;
      this.time = obj.time;
   }
   function set _name(value)
   {
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
