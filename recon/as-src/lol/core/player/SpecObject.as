class lol.core.player.SpecObject
{
   var _xp_specs;
   var dispatchEvent;
   var id;
   var title;
   var xp_max_specs;
   static var INCREASE_SPEC = "INCREASE_SPEC";
   static var INCREASE_SPEC_LEVEL = "INCREASE_SPEC_LEVEL";
   var value = 0;
   var _value_bonus = 0;
   var min_skill_level = 0;
   function SpecObject()
   {
      lol.events.LEventDispatcher.initialize(this);
      this.id = arguments[0];
      this.value = arguments[1];
      this.currentValue = arguments[2];
      this.title = arguments[3];
      this.available = arguments[4];
      this.min_skill_level = arguments[5];
   }
   function get currentValue()
   {
      var _loc2_;
      if(this.value >= 0)
      {
         _loc2_ = Math.round(this.xp_specs * 100 / this.xp_max_specs);
         return _loc2_;
      }
      return undefined;
   }
   function set value_bonus(num)
   {
      if(this.value_bonus != num && this.value_bonus != undefined && (this.value_bonus != 0 || num - this.value_bonus < 2))
      {
         this.dispatchEvent({type:lol.core.player.SpecObject.INCREASE_SPEC_LEVEL,value:num});
      }
      this._value_bonus = num;
   }
   function get value_bonus()
   {
      return this._value_bonus;
   }
   function set xp_specs(value)
   {
      var _loc3_;
      if(value > this.xp_specs)
      {
         _loc3_ = value - this.xp_specs;
         this.dispatchEvent({type:lol.core.player.SpecObject.INCREASE_SPEC,value:_loc3_});
      }
      this._xp_specs = value;
   }
   function get xp_specs()
   {
      return this._xp_specs;
   }
   function get level()
   {
      if(this.value >= 0)
      {
         return this.value_bonus;
      }
      return this.value;
   }
   function get available()
   {
      if(this.value >= 0)
      {
         return true;
      }
      return false;
   }
}
