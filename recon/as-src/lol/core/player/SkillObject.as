class lol.core.player.SkillObject
{
   var _value_bonus;
   var _xp_skills;
   var dispatchEvent;
   var specArr;
   var xp_max_skills;
   static var INCREASE_LEVEL = "INCREASE_LEVEL";
   static var INCREASE_SKILL = "INCREASE_SKILL";
   function SkillObject()
   {
      lol.events.LEventDispatcher.initialize(this);
      this.specArr = new Array();
   }
   function set value_bonus(num)
   {
      if(this.value_bonus != num && this.value_bonus != undefined && (this.value_bonus != 0 || num - this.value_bonus < 2))
      {
         this.dispatchEvent({type:lol.core.player.SkillObject.INCREASE_LEVEL,value:num});
      }
      this._value_bonus = num;
   }
   function get value_bonus()
   {
      return this._value_bonus;
   }
   function get currentValue()
   {
      var _loc2_ = Math.round(this.xp_skills * 100 / this.xp_max_skills);
      return _loc2_;
   }
   function set xp_skills(value)
   {
      var _loc3_;
      if(value > this.xp_skills && value != undefined && this.xp_skills != undefined)
      {
         _loc3_ = value - this.xp_skills;
         this.dispatchEvent({type:lol.core.player.SkillObject.INCREASE_SKILL,value:_loc3_});
      }
      this._xp_skills = value;
   }
   function get xp_skills()
   {
      return this._xp_skills;
   }
   function get level()
   {
      return this.value_bonus;
   }
   function get levelString()
   {
      var _loc2_ = this.skillString(this.level);
      return _loc2_;
   }
   function skillString(num)
   {
      var _loc3_;
      if(num >= 0 && num <= 4)
      {
         _loc3_ = "Новичок";
      }
      else if(num >= 5 && num <= 9)
      {
         _loc3_ = "Ученик";
      }
      else if(num >= 10 && num <= 14)
      {
         _loc3_ = "Любитель";
      }
      else if(num >= 15 && num <= 19)
      {
         _loc3_ = "Профи";
      }
      else if(num >= 20)
      {
         _loc3_ = "Гуру";
      }
      _loc3_ = num + " ( " + _loc3_ + " ), " + this.xp_skills + " из " + this.xp_max_skills + " ( " + this.currentValue + "% )";
      return _loc3_;
   }
}
