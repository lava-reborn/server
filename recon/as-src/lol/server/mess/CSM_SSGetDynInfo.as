class lol.server.mess.CSM_SSGetDynInfo extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_SSGetDynInfo(obj, target)
   {
      super();
      this._name = "ss_get_di";
      if(target)
      {
         this.addProp("target",target);
      }
      this.addProp("obj",obj);
   }
}
