class lol.server.mess.CSM_M_sndml extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_M_sndml(to, subj, type, body, item, afro, gold)
   {
      super();
      this._name = "sndml";
      if(gold)
      {
         this.addProp("gold",gold);
      }
      if(afro)
      {
         this.addProp("afro",afro);
      }
      var _loc3_;
      if(item)
      {
         _loc3_ = 0;
         while(_loc3_ < item.length)
         {
            this.addProp("item",item[_loc3_],"item" + _loc3_);
            _loc3_ = _loc3_ + 1;
         }
      }
      this.addProp("body",body);
      this.addProp("type",type);
      this.addProp("subj",subj);
      this.addProp("to",to);
   }
}
