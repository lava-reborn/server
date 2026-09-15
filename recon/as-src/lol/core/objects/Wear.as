class lol.core.objects.Wear extends lol.core.objects.Item implements lol.core.objects.Breakable
{
   var __break;
   var armor_class;
   var getProp;
   var max_break_abs;
   var max_break_cur;
   var name;
   var parseNeedBonus;
   var setInfo;
   var setProp;
   var setTypeID;
   var slot_type;
   var sub_name;
   static var MOD_ARR;
   static var className = "Wear";
   var __className = "Wear";
   function Wear(ID, _typeID, _rooID)
   {
      super(ID,_typeID,_rooID);
      lol.core.objects.Wear.MOD_ARR = new Array();
      lol.core.objects.Wear.MOD_ARR.NY0 = "1";
      lol.core.objects.Wear.MOD_ARR.NY1 = "2";
      lol.core.objects.Wear.MOD_ARR.NY2 = "3";
      lol.core.objects.Wear.MOD_ARR.NY3 = "4";
      lol.core.objects.Wear.MOD_ARR.NY4 = "5";
      lol.core.objects.Wear.MOD_ARR.NY5 = "6";
      lol.core.objects.Wear.MOD_ARR.NY6 = "7";
      lol.core.objects.Wear.MOD_ARR.NY7 = "8";
      lol.core.objects.Wear.MOD_ARR.NY8 = "9";
      lol.core.objects.Wear.MOD_ARR.NY9 = "10";
      lol.core.objects.Wear.MOD_ARR.NY10 = "11";
      lol.core.objects.Wear.MOD_ARR.NY11 = "12";
      lol.core.objects.Wear.MOD_ARR.NY12 = "13";
      lol.core.objects.Wear.MOD_ARR.NY13 = "14";
      lol.core.objects.Wear.MOD_ARR.NY14 = "15";
      lol.core.objects.Wear.MOD_ARR.NY15 = "16";
      lol.core.objects.Wear.MOD_ARR.NY16 = "17";
      lol.core.objects.Wear.MOD_ARR.NY17 = "18";
      lol.core.objects.Wear.MOD_ARR.NY18 = "19";
      lol.core.objects.Wear.MOD_ARR.NY19 = "20";
      lol.core.objects.Wear.MOD_ARR.NY20 = "21";
   }
   function initialize(obj)
   {
      this.armor_class = obj.armor_class;
      this.slot_type = obj.slot_type;
      this.max_break_abs = obj.max_break_abs;
      this.setTypeID = obj.set_type;
      if(this.setTypeID)
      {
         this.setInfo = lol.core.sets.SetManager.getSet(this.setTypeID);
      }
      this.parseNeedBonus(obj);
      super.initialize(obj);
   }
   function set _name(value)
   {
      var _loc3_ = value.indexOf("$",0);
      var _loc4_;
      if(_loc3_ != -1)
      {
         _loc4_ = value.substr(_loc3_ + 1,value.length);
         this.setProp("sub_name",_loc4_);
         value = value.substr(0,_loc3_);
         this.sub_name = _loc4_;
      }
      this.name = value;
   }
   function getCurQuality()
   {
      var _loc3_ = this.getProp("__break");
      var _loc2_ = this.getProp("max_break_cur");
      return _loc3_ / _loc2_;
   }
   function getAbsQuality()
   {
      var _loc3_ = this.getProp("__break");
      var _loc2_ = this.getProp("max_break_abs");
      return _loc3_ / _loc2_;
   }
   function get armorClass()
   {
      return this.getProp("armor_class");
   }
   function set armorClass(tArmorClass)
   {
      this.setProp("armor_class",tArmorClass);
   }
   function get slotType()
   {
      return this.getProp("slot_type");
   }
   function set slotType(tSlotType)
   {
      this.setProp("slot_type",tSlotType);
   }
   function get _break()
   {
      return this.__break;
   }
   function set _break(tBreak)
   {
      this.__break = tBreak;
   }
   function get maxBreakCur()
   {
      return this.max_break_cur;
   }
   function set maxBreakCur(tMaxBreakCur)
   {
      this.max_break_cur = tMaxBreakCur;
   }
   function get needAttribs()
   {
      return this.getProp("need_attribs");
   }
   function set needAttribs(tNeedAttribs)
   {
      this.setProp("need_attribs",tNeedAttribs);
   }
   function get needSkills()
   {
      return this.getProp("need_skills");
   }
   function set needSkills(tNeedSkills)
   {
      this.setProp("need_skills",tNeedSkills);
   }
   function get needSpecs()
   {
      return this.getProp("need_specs");
   }
   function set needSpecs(tNeedSpecs)
   {
      this.setProp("need_specs",tNeedSpecs);
   }
   function get maxBreakAbs()
   {
      return this.max_break_abs;
   }
   function set maxBreakAbs(tMaxBreakAbs)
   {
      this.max_break_abs = tMaxBreakAbs;
   }
}
